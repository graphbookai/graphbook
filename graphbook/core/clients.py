from typing import List, Dict, Optional, Any
import uuid
from aiohttp.web import WebSocketResponse
from .processing.web_processor import WebInstanceProcessor
from .nodes import NodeHub
from .viewer import MultiGraphViewManager
import tempfile
import os.path as osp
from pathlib import Path
import multiprocessing as mp
import os
import asyncio
import shutil
import traceback
import sys
from .utils import TaskLoop


DEFAULT_CLIENT_OPTIONS = {"SEND_EVERY": 0.5}


class ProcessorInterface:
    def get_output(self, step_id: str, pin_id: str, index: int) -> dict:
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def get_queue(self) -> mp.Queue:
        raise NotImplementedError

    def handle_prompt_response(self, response: dict):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


class Client:
    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        view_manager: MultiGraphViewManager,
        proc_interface: ProcessorInterface,
    ):
        self.sid = sid
        self.ws = ws
        # graph_id -> {state_type -> idx}
        self.state_idx: Dict[str, Dict[str, int]] = {}
        self.state_idx_global: Dict[str, int] = {}
        self.log_idx: Dict[str, int] = {}
        self.view_manager = view_manager
        self.proc_interface = proc_interface
        
    def reset_log_idx(self):
        """Reset the log index to 0 when clear outputs is called"""
        self.log_idx = {}

    def get_view_manager(self) -> MultiGraphViewManager:
        return self.view_manager

    def get_processor(self) -> ProcessorInterface:
        return self.proc_interface

    async def close(self):
        await self.ws.close()


class WebClient(Client):
    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        processor: WebInstanceProcessor,
        node_hub: NodeHub,
        view_manager: MultiGraphViewManager,
        setup_paths: dict,
    ):
        super().__init__(sid, ws, view_manager, processor)
        self.processor = processor
        self.node_hub = node_hub
        self.root_path = Path(setup_paths["workflow_dir"])
        self.docs_path = Path(setup_paths["docs_path"])
        self.custom_nodes_path = Path(setup_paths["custom_nodes_path"])

    def get_root_path(self) -> Optional[Path]:
        return self.root_path

    def get_docs_path(self) -> Optional[Path]:
        return self.docs_path

    def get_custom_nodes_path(self) -> Optional[Path]:
        return self.custom_nodes_path

    def nodes(self):
        return self.node_hub.get_exported_nodes()

    def exec(self, req: dict):
        self.processor.exec(req)

    def get_node_hub(self) -> NodeHub:
        return self.node_hub


class ClientPool(TaskLoop):
    def __init__(
        self,
        close_event: mp.Event,
        options: dict = DEFAULT_CLIENT_OPTIONS,
    ):
        self.clients: Dict[str, Client] = {}
        self.ws: Dict[str, WebSocketResponse] = {}
        self.tmpdirs: Dict[str, str] = {}
        self.close_event = close_event
        self.options = options
        super().__init__(options["SEND_EVERY"], close_event)

    async def add_client(self, ws: WebSocketResponse) -> Client:
        raise NotImplementedError

    async def loop(self):
        raise NotImplementedError

    def get_state_data(
        self, view_manager: MultiGraphViewManager, client: Client
    ) -> List[dict]:
        states = view_manager.get_current_states(
            client.state_idx, client.state_idx_global
        )

        for idx, data in states:
            graph_id, type = data.get("graph_id"), data["type"]

            if graph_id is None:
                client.state_idx_global[type] = idx
            else:
                if graph_id not in client.state_idx:
                    client.state_idx[graph_id] = {}
                client.state_idx[graph_id][type] = idx

        return_data = [data for _, data in states]
        return return_data
        
    def get_logs_data(
        self, view_manager: MultiGraphViewManager, client: Client
    ) -> List[dict]:
        """Get new logs for a client and update their log index"""
        graph_logs = []
        for graph_id, log_viewer in view_manager.log_viewers.items():
            if client.log_idx.get(graph_id) is None:
                client.log_idx[graph_id] = 0
            logs = log_viewer.get_logs_since_idx(client.log_idx[graph_id])
            if logs:
                # Update client's log index
                client.log_idx[graph_id] = len(log_viewer.logs)
                # Format logs data for transmission
                graph_logs.append({"type": "logs", "graph_id": graph_id, "data": logs})
        return graph_logs

    async def remove_client(self, client: Client):
        sid = client.sid
        if sid in self.clients:
            del self.clients[sid]
        if sid in self.ws:
            del self.ws[sid]
        if sid in self.tmpdirs:
            shutil.rmtree(self.tmpdirs[sid])
            del self.tmpdirs[sid]

    def get(self, sid: str) -> Optional[Client]:
        return self.clients.get(sid, None)


class AppClientPool(ClientPool):
    def __init__(
        self,
        close_event: mp.Event,
        web_processor_args: dict,
        plugins: tuple,
        no_sample: bool,
        setup_paths: dict,
    ):
        super().__init__(close_event, options=DEFAULT_CLIENT_OPTIONS)
        self.web_processor_args = web_processor_args
        self.web_processor_args["close_event"] = self.close_event
        self.setup_paths = setup_paths
        self.custom_nodes_path = (
            setup_paths["custom_nodes_path"] if setup_paths else None
        )
        self.plugins = plugins
        self.no_sample = no_sample
        sys.path.append(str(self.setup_paths["workflow_dir"]))

    def _create_resources(
        self, web_processor_args: dict, custom_nodes_path: Optional[str] = None
    ):
        view_queue = mp.Queue()
        processor_args = {
            **web_processor_args,
            "workflow_path": Path(self.setup_paths["workflow_dir"]),
            "custom_nodes_path": custom_nodes_path,
            "view_manager_queue": view_queue,
        }
        processor = WebInstanceProcessor(**processor_args)
        view_manager = MultiGraphViewManager(view_queue, processor, self.close_event)
        node_hub = NodeHub(self.plugins, view_manager, custom_nodes_path)
        return {
            "processor": processor,
            "node_hub": node_hub,
            "view_manager": view_manager,
        }

    def _create_dirs(
        self,
        workflow_dir: str,
        custom_nodes_path: str,
        docs_path: str,
        copy_dir: Optional[str] = None,
    ):
        def create_sample_workflow():
            import shutil

            project_path = Path(__file__).parent
            assets_dir = project_path.joinpath("sample_assets")
            n = "SampleWorkflow.json"
            shutil.copyfile(assets_dir.joinpath(n), Path(workflow_dir).joinpath(n))
            n = "SampleWorkflow.md"
            shutil.copyfile(assets_dir.joinpath(n), Path(docs_path).joinpath(n))
            n = "sample_nodes.py"
            shutil.copyfile(assets_dir.joinpath(n), Path(custom_nodes_path).joinpath(n))

        if copy_dir:
            if osp.exists(copy_dir):
                shutil.copytree(copy_dir, workflow_dir)
                return

        should_create_sample = False
        if not osp.exists(workflow_dir):
            should_create_sample = not self.no_sample
            os.mkdir(workflow_dir)
        if not osp.exists(custom_nodes_path):
            os.mkdir(custom_nodes_path)
        if not osp.exists(docs_path):
            os.mkdir(docs_path)

        if should_create_sample:
            create_sample_workflow()

    async def add_client(self, ws: WebSocketResponse) -> Client:
        sid = uuid.uuid4().hex
        setup_paths = {**self.setup_paths}
        root_path = Path(tempfile.mkdtemp())
        self.tmpdirs[sid] = root_path
        setup_paths = {
            key: root_path.joinpath(path) for key, path in setup_paths.items()
        }
        custom_nodes_path = setup_paths["custom_nodes_path"] if setup_paths else None
        web_processor_args = {
            **self.web_processor_args,
            "custom_nodes_path": custom_nodes_path,
        }
        self._create_dirs(
            **setup_paths, copy_dir="./workflow" if self.no_sample else None
        )
        resources = self._create_resources(web_processor_args, custom_nodes_path)

        client = WebClient(sid, ws, **resources, setup_paths=setup_paths)
        print(f"{sid}: {client.get_root_path()}")

        self.clients[sid] = client
        self.ws[sid] = ws
        resources["processor"].start()
        resources["node_hub"].start()
        resources["view_manager"].start()

        await ws.send_json({"type": "sid", "data": sid})
        return client

    # if stop_resources == True, will crash graphbook
    async def remove_client(self, client: WebClient, stop_resources: bool = False):
        sid = client.sid
        await client.close()
        if stop_resources:
            client.get_processor().stop()
            await client.get_view_manager().stop()
            client.get_node_hub().stop()
        if sid in self.clients:
            del self.clients[sid]
        if sid in self.ws:
            del self.ws[sid]
        if sid in self.tmpdirs:
            shutil.rmtree(self.tmpdirs[sid])
            del self.tmpdirs[sid]

    async def loop(self):
        try:
            for client in list(self.clients.values()):
                if client.ws.closed:
                    continue
                view_manager = client.get_view_manager()
                view_data = view_manager.get_current_view_data()
                state_data = self.get_state_data(view_manager, client)
                
                # Get new logs for this client
                logs_data = self.get_logs_data(view_manager, client)
                
                try:
                    client_data = [*view_data, *state_data, *logs_data]
                    if len(client_data) > 0:
                        await asyncio.gather(
                            *[client.ws.send_json(data) for data in client_data]
                        )
                except Exception as e:
                    print(f"Error sending to client: {e}")
        except Exception as e:
            print(f"ClientPool Error:")
            traceback.print_exc()
            raise

    async def stop(self):
        await super().stop()
        for client in list(self.clients.values()):
            await self.remove_client(client)


class SimpleClient(Client):
    """
    A simple client that only needs to handle websocket communications.
    No file system paths are required.
    """

    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        view_manager: MultiGraphViewManager,
        processor: Any,  # GraphProcessor
    ):
        super().__init__(sid, ws, view_manager, processor)
        self.processor = processor

    def exec(self, req: dict):
        # No-op as GraphProcessor doesn't use a command queue
        pass

    def get_processor(self):
        return self.processor


class SimpleClientPool(ClientPool):
    """
    A simple client pool that only needs to manage websocket connections.
    No file system paths or node hubs are required.
    """

    def __init__(
        self,
        close_event: mp.Event,
        view_queue: mp.Queue,
        processor: Any,  # GraphProcessor
    ):
        super().__init__(close_event)
        self.view_manager = MultiGraphViewManager(view_queue, processor, close_event)
        self.processor = processor

    async def add_client(self, ws: WebSocketResponse) -> Client:
        sid = uuid.uuid4().hex
        client = SimpleClient(sid, ws, self.view_manager, self.processor)
        print(f"{sid}: SimpleClient")

        self.clients[sid] = client
        self.ws[sid] = ws
        await ws.send_json({"type": "sid", "data": sid})
        return client

    async def loop(self):
        view_data = self.view_manager.get_current_view_data()
        for client in list(self.clients.values()):
            if client.ws.closed:
                continue
            state_data = self.get_state_data(self.view_manager, client)
            
            # Get new logs for this client
            logs_data = self.get_logs_data(self.view_manager, client)
            
            try:
                client_data = [*view_data, *state_data, *logs_data]
                if len(client_data) > 0:
                    await asyncio.gather(
                        *[client.ws.send_json(data) for data in client_data]
                    )
            except Exception as e:
                print(f"Error sending to client: {e}")

    def start(self):
        super().start()
        self.view_manager.start()


class AppSharedClientPool(AppClientPool):
    def __init__(
        self,
        close_event: mp.Event,
        web_processor_args: dict,
        plugins: tuple,
        no_sample: bool,
        setup_paths: dict,
    ):
        super().__init__(
            close_event, web_processor_args, plugins, no_sample, setup_paths
        )
        self._create_dirs(**setup_paths)
        self.shared_resources = self._create_resources(
            web_processor_args, self.custom_nodes_path
        )

    async def add_client(self, ws: WebSocketResponse) -> Client:
        sid = uuid.uuid4().hex
        setup_paths = {**self.setup_paths}
        resources = self.shared_resources
        client = WebClient(sid, ws, **resources, setup_paths=setup_paths)
        print(f"{sid}: {client.get_root_path()}")

        self.clients[sid] = client
        self.ws[sid] = ws
        await ws.send_json({"type": "sid", "data": sid})
        return client

    async def remove_client(self, client):
        return await super().remove_client(client, False)

    async def loop(self):
        view_manager: MultiGraphViewManager = self.shared_resources["view_manager"]
        view_data = view_manager.get_current_view_data()
        for client in list(self.clients.values()):
            if client.ws.closed:
                continue
            state_data = self.get_state_data(view_manager, client)
            
            # Get new logs for this client
            logs_data = self.get_logs_data(view_manager, client)
            
            try:
                client_data = [*view_data, *state_data, *logs_data]
                if len(client_data) > 0:
                    await asyncio.gather(
                        *[client.ws.send_json(data) for data in client_data]
                    )
            except Exception as e:
                print(f"Error sending to client: {e}")

    async def stop(self):
        await super().stop()
        self.shared_resources["processor"].stop()
        self.shared_resources["node_hub"].stop()
        self.shared_resources["view_manager"].stop()

    def start(self):
        super().start()
        viewer = self.shared_resources.get("view_manager")
        if viewer:
            viewer.start()

        processor = self.shared_resources.get("processor")
        if processor:
            processor.start()

        node_hub = self.shared_resources.get("node_hub")
        if node_hub:
            node_hub.start()

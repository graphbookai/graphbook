from typing import List, Dict, Optional
import uuid
from aiohttp.web import WebSocketResponse
from .processing.web_processor import WebInstanceProcessor
from .nodes import NodeHub
from .viewer import MultiGraphViewManager
from .logger import LogDirectoryReader
import tempfile
import os.path as osp
from pathlib import Path
import multiprocessing as mp
import os
import asyncio
import shutil
import traceback
from .utils import TaskLoop, RAY

DEFAULT_CLIENT_OPTIONS = {"SEND_EVERY": 0.5}


class ProcessorInterface:
    def get_output_note(self, step_id: str, pin_id: str, index: int) -> dict:
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def get_queue(self) -> mp.Queue:
        raise NotImplementedError

    def handle_prompt_response(self, response: dict):
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
        self.view_manager = view_manager
        # graph_id -> {state_type -> idx}
        self.state_idx: Dict[str, Dict[str, int]] = {}
        self.state_idx_global: Dict[str, int] = {}
        self.proc_interface = proc_interface

    def get_view_manager(self) -> MultiGraphViewManager:
        return self.view_manager

    def get_processor(self) -> ProcessorInterface:
        return self.proc_interface
    
    def start(self):
        self.view_manager.start()

    async def stop(self):
        await self.view_manager.stop()

    async def close(self):
        await self.ws.close()


class RayProcessorInterface:
    def __init__(self, processor, proc_queue: mp.Queue):
        self.processor = processor
        self.queue = proc_queue

    def get_output_note(self, step_id: str, pin_id: str, index: int):
        return RAY.get(self.processor.get_output_note.remote(step_id, pin_id, index))

    def pause(self):
        raise NotImplementedError("RayProcessor does not support pause")

    def get_queue(self):
        return self.queue


class RayClient(Client):
    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        view_manager: MultiGraphViewManager,
        proc_queue: mp.Queue,
    ):
        processor = RAY.get_actor("_graphbook_RayStepHandler")
        self.processor_interface = RayProcessorInterface(processor, proc_queue)
        super().__init__(sid, ws, view_manager, self.processor_interface)


class WebClient(Client):
    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        processor: WebInstanceProcessor,
        node_hub: NodeHub,
        view_manager: MultiGraphViewManager,
        log_handler: Optional[LogDirectoryReader] = None,
        setup_paths: Optional[dict] = None,
    ):
        super().__init__(sid, ws, view_manager, processor)
        self.processor = processor
        self.node_hub = node_hub
        self.log_handler = log_handler
        if setup_paths:
            self.root_path = Path(setup_paths["workflow_dir"])
            self.docs_path = Path(setup_paths["docs_path"])
            self.custom_nodes_path = Path(setup_paths["custom_nodes_path"])
        else:
            self.root_path = None
            self.docs_path = None
            self.custom_nodes_path = None

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
    
    def get_logger(self) -> Optional[LogDirectoryReader]:
        return self.log_handler
    
    def start(self):
        self.processor.start()
        self.node_hub.start()
        # if self.log_handler: Not available in isolated mode
        #     self.log_handler.start()
        super().start()

    async def stop(self):
        self.processor.stop()
        self.node_hub.stop()
        if self.log_handler:
            self.log_handler.stop()
        await super().stop()


class ClientPool(TaskLoop):
    def __init__(
        self,
        web_processor_args: dict,
        plugins: tuple,
        isolate_users: bool,
        no_sample: bool,
        close_event: mp.Event,
        log_dir: Optional[str] = None,
        setup_paths: Optional[dict] = None,
        proc_queue: Optional[mp.Queue] = None,
        view_queue: Optional[mp.Queue] = None,
        options: dict = DEFAULT_CLIENT_OPTIONS,
    ):
        self.clients: Dict[str, Client] = {}
        self.ws: Dict[str, WebSocketResponse] = {}
        self.tmpdirs: Dict[str, str] = {}
        self.web_processor_args = web_processor_args
        self.web_processor_args["close_event"] = close_event
        self.setup_paths = setup_paths
        self.is_interactive = setup_paths is not None
        self.custom_nodes_path = (
            setup_paths["custom_nodes_path"] if setup_paths else None
        )
        self.log_dir = log_dir
        self.plugins = plugins
        self.shared_execution = not isolate_users
        self.no_sample = no_sample
        self.close_event = close_event
        self.proc_queue = proc_queue
        self.view_queue = view_queue
        self.options = options
        if self.shared_execution:
            if setup_paths:
                self._create_dirs(**setup_paths)
            self.shared_resources = self._create_resources(
                web_processor_args, self.custom_nodes_path
            )
        super().__init__(options["SEND_EVERY"], close_event)

    def _create_resources(
        self, web_processor_args: dict, custom_nodes_path: Optional[str] = None
    ):
        view_queue = self.view_queue if self.view_queue is not None else mp.Queue()
        if self.is_interactive:
            processor_args = {
                **web_processor_args,
                "custom_nodes_path": custom_nodes_path,
                "view_manager_queue": view_queue,
            }
            processor = WebInstanceProcessor(**processor_args)
            view_manager = MultiGraphViewManager(
                view_queue, processor, self.close_event
            )
            node_hub = NodeHub(self.plugins, view_manager, custom_nodes_path)
            log_handler = None
            if self.log_dir:
                log_handler = LogDirectoryReader(self.log_dir, view_queue, close_event=self.close_event)
            return {
                "processor": processor,
                "node_hub": node_hub,
                "view_manager": view_manager,
                "log_handler": log_handler,
            }

        view_manager = MultiGraphViewManager(view_queue, close_event=self.close_event)
        return {
            "view_manager": view_manager,
        }

    def _create_dirs(
        self, workflow_dir: str, custom_nodes_path: str, docs_path: str
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

        if not self.shared_execution and self.no_sample:
            if osp.exists("./workflow"):
                shutil.copytree("./workflow", workflow_dir)
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
        setup_paths = {**self.setup_paths} if self.setup_paths else None
        if self.shared_execution:
            resources = self.shared_resources
        else:
            root_path = Path(tempfile.mkdtemp())
            self.tmpdirs[sid] = root_path
            setup_paths = {
                key: root_path.joinpath(path) for key, path in setup_paths.items()
            }
            custom_nodes_path = (
                setup_paths["custom_nodes_path"] if setup_paths else None
            )
            web_processor_args = {
                **self.web_processor_args,
                "custom_nodes_path": custom_nodes_path,
            }
            self._create_dirs(**setup_paths)
            resources = self._create_resources(web_processor_args, custom_nodes_path)

        if self.is_interactive:
            client = WebClient(sid, ws, **resources, setup_paths=setup_paths)
            print(f"{sid}: {client.get_root_path()}")
        else:
            client = RayClient(sid, ws, **resources, proc_queue=self.proc_queue)
            print(f"{sid}: (non-interactive)")
        self.clients[sid] = client
        self.ws[sid] = ws
        if not self.shared_execution:
            client.start()
        await ws.send_json({"type": "sid", "data": sid})
        return client

    def get(self, sid: str) -> Optional[Client]:
        return self.clients.get(sid, None)

    def get_all(self) -> List[Client]:
        return list(self.clients.values())

    def get_all_ws(self) -> Dict[str, WebSocketResponse]:
        return self.ws

    async def remove_client(self, client: Client):
        sid = client.sid
        await client.close()
        # if not self.shared_execution: #TODO: Fix from blocking
            # await client.stop()
        if sid in self.clients:
            del self.clients[sid]
        if sid in self.ws:
            del self.ws[sid]
        if sid in self.tmpdirs:
            shutil.rmtree(self.tmpdirs[sid])
            del self.tmpdirs[sid]

    async def stop(self):
        for client in list(self.clients.values()):
            await self.remove_client(client)
        if self.shared_execution:
            self.shared_resources["processor"].stop()
            self.shared_resources["node_hub"].stop()
            self.shared_resources["view_manager"].stop()
            self.shared_resources["log_handler"].stop()

    async def loop(self):
        def get_state_data(
            view_manager: MultiGraphViewManager, client: Client
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

        try:
            if self.shared_execution:
                view_manager: MultiGraphViewManager = self.shared_resources[
                    "view_manager"
                ]
                view_data = view_manager.get_current_view_data()
                for client in list(self.clients.values()):
                    if client.ws.closed:
                        continue
                    state_data = get_state_data(view_manager, client)
                    try:
                        await asyncio.gather(
                            *[
                                client.ws.send_json(data)
                                for data in [*view_data, *state_data]
                            ]
                        )
                    except Exception as e:
                        print(f"Error sending to client: {e}")
            else:
                for client in list(self.clients.values()):
                    if client.ws.closed:
                        continue
                    view_manager = client.get_view_manager()
                    view_data = view_manager.get_current_view_data()
                    state_data = get_state_data(view_manager, client)
                    try:
                        await asyncio.gather(
                            *[
                                client.ws.send_json(data)
                                for data in [*view_data, *state_data]
                            ]
                        )
                    except Exception as e:
                        print(f"Error sending to client: {e}")
        except Exception as e:
            print(f"ClientPool Error:")
            traceback.print_exc()
            raise

    def start(self):
        super().start()
        if self.shared_execution:
            viewer = self.shared_resources.get("view_manager")
            if viewer:
                viewer.start()

            processor = self.shared_resources.get("processor")
            if processor:
                processor.start()

            node_hub = self.shared_resources.get("node_hub")
            if node_hub:
                node_hub.start()

            log_handler = self.shared_resources.get("log_handler")
            if log_handler:
                log_handler.start()

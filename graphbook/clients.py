from typing import Dict
import uuid
from aiohttp.web import WebSocketResponse
from .processing.web_processor import WebInstanceProcessor, poll_conn_for
from .utils import ProcessorStateRequest
from .exports import NodeHub
from .viewer import ViewManager
import tempfile
import os.path as osp
import multiprocessing as mp
import os
import asyncio


class Client:
    def __init__(
        self,
        ws: WebSocketResponse,
        processor: WebInstanceProcessor,
        node_hub: NodeHub,
        view_manager: ViewManager,
        root_path: str,
    ):
        self.ws = ws
        self.processor = processor
        self.node_hub = node_hub
        self.view_manager = view_manager
        self.root_path = root_path

    def get_root_path(self):
        return self.root_path

    def nodes(self):
        return self.node_hub.get_exported_nodes()

    def step_doc(self, name):
        return self.node_hub.get_step_docstring(name)

    def resource_doc(self, name):
        return self.node_hub.get_resource_docstring(name)

    def poll(self, cmd: ProcessorStateRequest, data: dict):
        res = poll_conn_for(
            self.conn,
            cmd,
            data,
        )
        return res

    def close(self):
        asyncio.create_task(self.ws.close())
        self.processor.close()
        self.view_manager.close()
        self.node_hub.stop()


class ClientPool:
    def __init__(
        self,
        web_processor_args: dict,
        setup_paths: dict,
        plugins: tuple,
        isolate_users: bool,
        no_sample: bool,
        close_event: mp.Event,
    ):
        self.clients: Dict[str, Client] = {}
        self.tmpdirs: Dict[str, str] = {}
        self.web_processor_args = web_processor_args
        self.setup_paths = setup_paths
        self.plugins = plugins
        self.shared_execution = not isolate_users
        self.no_sample = no_sample
        self.close_event = close_event
        if self.shared_execution:
            self.shared_resources = self._create_resources(
                web_processor_args, setup_paths
            )

    def _create_resources(self, web_processor_args: dict, setup_paths: dict):
        proc_queue = mp.Queue()
        view_queue = mp.Queue()
        parent_conn, child_conn = mp.Pipe()
        pause_event = mp.Event()
        processor_args = {
            **web_processor_args,
            "cmd_queue": proc_queue,
            "server_request_conn": child_conn,
            "view_manager_queue": view_queue,
            "pause_event": pause_event,
        }
        processor = WebInstanceProcessor(**processor_args)
        node_hub = NodeHub(setup_paths["custom_nodes_path"], self.plugins)
        view_manager = ViewManager(view_queue, self.close_event, parent_conn)
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, view_manager.start)
        self._create_dirs(**setup_paths, no_sample=self.no_sample)
        return {
            "processor": processor,
            "node_hub": node_hub,
            "view_manager": view_manager,
        }

    def _create_dirs(self, workflow_dir, custom_nodes_path, docs_path, no_sample: bool):
        def create_sample_workflow():
            import shutil

            assets_dir = osp.join(osp.dirname(__file__), "sample_assets")
            n = "SampleWorkflow.json"
            shutil.copyfile(osp.join(assets_dir, n), osp.join(workflow_dir, n))
            n = "SampleWorkflow.md"
            shutil.copyfile(osp.join(assets_dir, n), osp.join(docs_path, n))
            n = "sample_nodes.py"
            shutil.copyfile(osp.join(assets_dir, n), osp.join(custom_nodes_path, n))

        should_create_sample = False
        if not osp.exists(workflow_dir):
            should_create_sample = not no_sample
            os.mkdir(workflow_dir)
        if not osp.exists(custom_nodes_path):
            os.mkdir(custom_nodes_path)
        if not osp.exists(docs_path):
            os.mkdir(docs_path)

        if should_create_sample:
            create_sample_workflow()

    def add_client(self, ws: WebSocketResponse) -> str:
        sid = uuid.uuid4().hex
        if not self.shared_execution:
            root_path = tempfile.mkdtemp()
            self.tmpdirs[sid] = root_path
            setup_paths = {**self.setup_paths}
            for key in setup_paths:
                setup_paths[key] = osp.join(root_path, setup_paths[key])
            web_processor_args = {
                **self.web_processor_args,
                "custom_nodes_path": setup_paths["custom_nodes_path"],
            }
            resources = self._create_resources(web_processor_args, setup_paths)
        else:
            resources = self.shared_resources

        resources["node_hub"].set_websocket(ws)  # Set the WebSocket in NodeHub
        resources["view_manager"].add_client(ws, sid)
        client = Client(ws, **resources, root_path=setup_paths["workflow_dir"])
        self.clients[sid] = client
        asyncio.create_task(ws.send_json({"type": "sid", "data": sid}))
        return sid

    async def remove_client(self, sid: str):
        if sid in self.clients:
            await self.clients[sid].close()
            del self.clients[sid]
        if sid in self.tmpdirs:
            os.rmdir(self.tmpdirs[sid])
            del self.tmpdirs[sid]

    def close_all(self):
        for sid in self.clients:
            self.clients[sid].close()
        for sid in self.tmpdirs:
            os.rmdir(self.tmpdirs[sid])
        self.clients = {}
        self.tmpdirs = {}

    def get_root_path(self, sid: str):
        if sid in self.clients:
            return self.clients[sid].get_root_path()

    def nodes(self, sid: str) -> dict:
        if sid in self.clients:
            return self.clients[sid].nodes()

    def step_doc(self, sid: str, name: str):
        if sid in self.clients:
            return self.clients[sid].step_doc(name)

    def resource_doc(self, sid: str, name: str):
        if sid in self.clients:
            return self.clients[sid].resource_doc(name)

    def exec(self, sid: str, data: dict):
        if sid in self.clients:
            self.clients[sid].exec(data)

    def poll(self, sid: str, cmd: ProcessorStateRequest, data: dict):
        if sid in self.clients:
            self.clients[sid].poll(cmd, data)

from typing import List, Dict
import uuid
from aiohttp.web import WebSocketResponse
from .processing.web_processor import WebInstanceProcessor
from .nodes import NodeHub
from .viewer import ViewManager
import tempfile
import os.path as osp
from pathlib import Path
import multiprocessing as mp
import os
import asyncio
import shutil

DEFAULT_CLIENT_OPTIONS = {"SEND_EVERY": 0.5}


class Client:
    def __init__(
        self,
        sid: str,
        ws: WebSocketResponse,
        processor: WebInstanceProcessor,
        node_hub: NodeHub,
        view_manager: ViewManager,
        setup_paths: dict,
    ):
        self.sid = sid
        self.ws = ws
        self.processor = processor
        self.node_hub = node_hub
        self.view_manager = view_manager
        self.root_path = Path(setup_paths["workflow_dir"])
        self.docs_path = Path(setup_paths["docs_path"])
        self.custom_nodes_path = Path(setup_paths["custom_nodes_path"])
        self.close_event = asyncio.Event()

    def get_root_path(self) -> Path:
        return self.root_path

    def get_docs_path(self) -> Path:
        return self.docs_path

    def get_custom_nodes_path(self) -> Path:
        return self.custom_nodes_path

    def nodes(self):
        return self.node_hub.get_exported_nodes()

    def step_doc(self, name):
        return self.node_hub.get_step_docstring(name)

    def resource_doc(self, name):
        return self.node_hub.get_resource_docstring(name)

    def exec(self, req: dict):
        self.processor.exec(req)

    def get_processor(self) -> WebInstanceProcessor:
        return self.processor

    def get_view_manager(self) -> ViewManager:
        return self.view_manager

    def get_node_hub(self) -> NodeHub:
        return self.node_hub

    async def close(self):
        await self.ws.close()


class ClientPool:
    def __init__(
        self,
        web_processor_args: dict,
        setup_paths: dict,
        plugins: tuple,
        isolate_users: bool,
        no_sample: bool,
        close_event: mp.Event,
        options: dict = DEFAULT_CLIENT_OPTIONS,
    ):
        self.clients: Dict[str, Client] = {}
        self.tmpdirs: Dict[str, str] = {}
        self.web_processor_args = web_processor_args
        self.setup_paths = setup_paths
        self.plugins = plugins
        self.shared_execution = not isolate_users
        self.no_sample = no_sample
        self.close_event = close_event
        self.options = options
        if self.shared_execution:
            self.shared_resources = self._create_resources(
                web_processor_args, setup_paths
            )
        self.curr_task = None

    def _create_resources(self, web_processor_args: dict, setup_paths: dict):
        view_queue = mp.Queue()
        processor_args = {
            **web_processor_args,
            "custom_nodes_path": setup_paths["custom_nodes_path"],
            "view_manager_queue": view_queue,
        }
        self._create_dirs(**setup_paths, no_sample=self.no_sample)
        processor = WebInstanceProcessor(**processor_args)
        view_manager = ViewManager(view_queue, processor)
        node_hub = NodeHub(setup_paths["custom_nodes_path"], self.plugins, view_manager)
        processor.start()
        view_manager.start()
        node_hub.start()
        return {
            "processor": processor,
            "node_hub": node_hub,
            "view_manager": view_manager,
        }

    def _create_dirs(
        self, workflow_dir: str, custom_nodes_path: str, docs_path: str, no_sample: bool
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

        if not self.shared_execution and no_sample:
            if osp.exists("./workflow"):
                shutil.copytree("./workflow", workflow_dir)
                return

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

    async def add_client(self, ws: WebSocketResponse) -> Client:
        sid = uuid.uuid4().hex
        setup_paths = {**self.setup_paths}
        if self.shared_execution:
            resources = self.shared_resources
        else:
            root_path = Path(tempfile.mkdtemp())
            self.tmpdirs[sid] = root_path
            setup_paths = {
                key: root_path.joinpath(path) for key, path in setup_paths.items()
            }
            web_processor_args = {
                **self.web_processor_args,
                "custom_nodes_path": setup_paths["custom_nodes_path"],
            }
            resources = self._create_resources(web_processor_args, setup_paths)

        client = Client(sid, ws, **resources, setup_paths=setup_paths)
        self.clients[sid] = client
        await ws.send_json({"type": "sid", "data": sid})
        print(f"{sid}: {client.get_root_path()}")
        return client

    def get(self, sid: str) -> Client | None:
        return self.clients.get(sid, None)

    async def remove_client(self, client: Client):
        sid = client.sid
        if sid in self.clients:
            await client.close()
            del self.clients[sid]
            if not self.shared_execution:
                client.get_processor().stop()
                client.get_node_hub().stop()
                client.get_view_manager().stop()
        if sid in self.tmpdirs:
            shutil.rmtree(self.tmpdirs[sid])
            del self.tmpdirs[sid]

    async def stop(self):
        for client in list(self.clients.values()):
            await self.remove_client(client)
        if self.curr_task:
            self.curr_task.cancel()
        if self.shared_execution:
            self.shared_resources["processor"].stop()
            self.shared_resources["node_hub"].stop()
            self.shared_resources["view_manager"].stop()

    async def _loop(self):
        def get_view_data(view_manager: ViewManager) -> List[dict]:
            current_view_data = view_manager.get_current_view_data()
            current_states = view_manager.get_current_states()
            return [*current_view_data, *current_states]

        while not self.close_event.is_set():
            await asyncio.sleep(self.options["SEND_EVERY"])

            if self.shared_execution:
                all_data = get_view_data(self.shared_resources["view_manager"])
                for client in self.clients.values():
                    try:
                        await asyncio.gather(
                            *[client.ws.send_json(data) for data in all_data]
                        )
                    except Exception as e:
                        print(f"Error sending to client: {e}")
            else:
                for client in self.clients.values():
                    all_data = get_view_data(client.get_view_manager())
                    try:
                        await asyncio.gather(
                            *[client.ws.send_json(data) for data in all_data]
                        )
                    except Exception as e:
                        print(f"Error sending to client: {e}")

    async def start(self):
        self.curr_task = asyncio.create_task(self._loop())

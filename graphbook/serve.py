import asyncio
from graphbook.processing.serve_processor import RemoteInstanceProcessor
from graphbook.media import create_media_server
from graphbook.transport import NetworkService
import multiprocessing as mp
import os, sys, signal
import os.path as osp


class GraphbookService:
    def __init__(self, host: str, port: int, processor_queue: mp.Queue):
        self.host = host
        self.port = port
        routes = {
            "DAG": self.handle_update_dag,
            "NOTE": self.handle_note,
            "RESOURCE": self.handle_resource,
            "RUN": self.handle_update_run,
            "STEP": self.handle_update_step,
            "CLEAR": self.handle_clear,
            "PAUSE": self.handle_pause,
        }
        self.network_service = NetworkService(host, port, routes)
        self.processor_queue = processor_queue

    def handle_update_dag(self, data: dict):
        graph = data.get("graph", {})
        resources = data.get("resources", {})
        step_id = data.get("step_id", "")
        filename = data.get("filename", "")
        self.processor_queue.put(
            {
                "cmd": "update_dag",
                "graph": graph,
                "resources": resources,
                "step_id": step_id,
                "filename": filename,
            }
        )

    def handle_update_run(self, data: dict):
        graph = data.get("graph", {})
        resources = data.get("resources", {})
        step_id = data.get("step_id", "")
        filename = data.get("filename", "")
        self.processor_queue.put(
            {
                "cmd": "handle_run",
                "graph": graph,
                "resources": resources,
                "step_id": step_id,
                "filename": filename,
            }
        )

    def handle_step(self, data: dict):
        graph = data.get("graph", {})
        resources = data.get("resources", {})
        step_id = data.get("step_id", "")
        filename = data.get("filename", "")
        self.processor_queue.put(
            {
                "cmd": "handle_step",
                "graph": graph,
                "resources": resources,
                "step_id": step_id,
                "filename": filename,
            }
        )

    def handle_note(self, data: dict):
        step_id = data.get("step_id", "")
        filename = data.get("filename", "")
        note = data.get("note", {})
        self.processor_queue.put(
            {
                "cmd": "handle_note",
                "step_id": step_id,
                "filename": filename,
                "note": note,
            }
        )

    def handle_resource(self, data: dict):
        node_id = data.get("node_id", "")
        resource = data.get("resource", {})
        self.processor_queue.put(
            {
                "cmd": "handle_resource",
                "node_id": node_id,
                "resource": resource,
            }
        )

    def handle_clear(self, data: dict):
        step_id = data.get("step_id", "")
        self.processor_queue.put(
            {
                "cmd": "handle_clear",
                "step_id": step_id,
            }
        )

    def handle_pause(self):
        self.processor_queue.put(
            {
                "cmd": "handle_pause",
            }
        )

    def start(self):
        print(f"Starting graphbook service at {self.host}:{self.port}")
        try:
            asyncio.run(self.network_service.start())
        except KeyboardInterrupt:
            print("Exiting media server")


def start_serve(args):
    cmd_queue = mp.Queue()
    parent_conn, child_conn = mp.Pipe()
    view_manager_queue = mp.Queue()
    close_event = mp.Event()
    pause_event = mp.Event()
    custom_nodes_path = args.nodes_dir
    if not osp.exists(custom_nodes_path):
        os.mkdir(custom_nodes_path)

    def create_service(host, port):
        svc = GraphbookService(host, port, cmd_queue)
        svc.start()

    processes = [
        mp.Process(target=create_media_server, args=(args,)),
        mp.Process(
            target=create_service,
            args=(
                args.host,
                args.port,
            ),
        ),
    ]

    for p in processes:
        p.daemon = True
        p.start()

    def signal_handler(*_):
        close_event.set()
        view_manager_queue.cancel_join_thread()
        cmd_queue.cancel_join_thread()
        for p in processes:
            p.join()
        cmd_queue.close()
        view_manager_queue.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    async def start():
        processor = RemoteInstanceProcessor(
            cmd_queue,
            parent_conn,
            view_manager_queue,
            args.continue_on_failure,
            args.copy_outputs,
            custom_nodes_path,
            close_event,
            pause_event,
            args.num_workers,
        )
        await processor.start_loop()

    asyncio.run(start())

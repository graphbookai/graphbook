import asyncio
from graphbook.remote_processing import RemoteInstanceProcessor
from graphbook.media import create_media_server
from graphbook.transport import NetworkService
import multiprocessing as mp
import os, sys, signal
import os.path as osp


class GraphbookService:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        routes = {
            "DAG": self.handle_update_dag,
            "NOTE": self.handle_note,
        }
        self.network_service = NetworkService(host, port, routes)

    def handle_update_dag(self, data):
        print("received dag update")

    def handle_note(self, note):
        print("received note")

    def start(self):
        print(f"Starting graphbook service at {self.host}:{self.port}")
        try:
            asyncio.run(self.network_service.start())
        except KeyboardInterrupt:
            print("Exiting media server")


def start_serve(args):
    def create_service(host, port):
        svc = GraphbookService(host, port)
        svc.start()

    cmd_queue = mp.Queue()
    parent_conn, child_conn = mp.Pipe()
    view_manager_queue = mp.Queue()
    close_event = mp.Event()
    pause_event = mp.Event()
    custom_nodes_path = args.nodes_dir
    if not osp.exists(custom_nodes_path):
        os.mkdir(custom_nodes_path)
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

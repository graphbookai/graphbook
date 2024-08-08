import asyncio
from graphbook.remote_processing import RemoteInstanceProcessor
from graphbook.media import create_media_server
import multiprocessing as mp
import os, sys, signal
import os.path as osp

class GraphbookService:
    def __init__(self):
        pass

    async def handle_update_state(self, data):
        # Assuming data is a dictionary for state updates
        self.graphbook.update_state(data)

    async def handle_add_note(self, note):
        # Assuming note is a string
        self.graphbook.add_note(note)

    async def handle_connection(self, reader, writer):
        data = await reader.read(100)
        message = data.decode()
        addr = writer.get_extra_info('peername')

        print(f"Received {message} from {addr}")

        # Simple protocol to determine action
        if message.startswith("UPDATE_STATE"):
            state_data = eval(message[len("UPDATE_STATE "):])
            await self.handle_update_state(state_data)
        elif message.startswith("ADD_NOTE"):
            note = message[len("ADD_NOTE "):]
            await self.handle_add_note(note)

        writer.close()
        
    async def _async_start(self):
        asyncio.run(start())
        service = GraphbookService()
        server = await asyncio.start_server(
            service.handle_connection, args.host, args.port)

        addr = server.sockets[0].getsockname()
        print(f'Serving on {addr}')

        async with server:
            await server.serve_forever()
        

    def start(self):
        print(f"Starting graphbook service at {self.host}:{self.port}")
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            print("Exiting media server")

def start_serve(args):
    def create_service():
        svc = GraphbookService()
        svc.start()

    cmd_queue = mp.Queue()
    parent_conn, child_conn = mp.Pipe()
    view_manager_queue = mp.Queue()
    close_event = mp.Event()
    pause_event = mp.Event()
    root_path = args.workflow_dir
    custom_nodes_path = args.nodes_dir
    if not osp.exists(root_path):
        os.mkdir(root_path)
    if not osp.exists(custom_nodes_path):
        os.mkdir(custom_nodes_path)
    processes = [
        mp.Process(target=create_media_server, args=(args,)),
        mp.Process(
            target=create_service,
            args=(
                args,
                cmd_queue,
                child_conn,
                pause_event,
                view_manager_queue,
                close_event,
                root_path,
                custom_nodes_path,
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

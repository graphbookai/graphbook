import asyncio
from asyncio.streams import StreamReader, StreamWriter
from graphbook.remote_processing import RemoteInstanceProcessor
from graphbook.media import create_media_server
import multiprocessing as mp
import os, sys, signal
import os.path as osp
import pickle
from typing import Tuple
import traceback


class GraphbookService:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def handle_update_dag(self, data):
        print("received dag update")

    def handle_note(self, note):
        print("received note")

    def handle_ok(self):
        print("received ok")

    async def get_packet(self, reader: StreamReader) -> Tuple[str, any] | None:
        try:
            data_header = await reader.readuntil()
            data_header = data_header.decode().strip()
            print(data_header)
            data_len = await reader.readuntil()
            data_len = int(data_len.decode().strip())
            print(data_len)
            if data_len == 0:
                return data_header, None
            payload = await reader.readexactly(data_len)
            print(len(payload))
            payload = pickle.loads(payload)
            print(payload.items)
            return data_header, payload
        except asyncio.exceptions.IncompleteReadError:
            return None
        except:
            traceback.print_exc()
            print("error reading data")
            return None

    async def handle_connection(self, reader: StreamReader, writer: StreamWriter):
        while not reader.at_eof():
            packet = await self.get_packet(reader)
            if packet is not None:
                header, payload = packet
                if header == "DAG":
                    self.handle_update_dag(payload)
                elif header == "NOTE":
                    self.handle_note(payload)
                elif header == "OK":
                    self.handle_ok()
                    writer.write("OK\n".encode())
                else:
                    print("Unknown header", header)

        writer.close()

    async def _async_start(self):
        server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )

        addr = server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        async with server:
            await server.serve_forever()

    def start(self):
        print(f"Starting graphbook service at {self.host}:{self.port}")
        try:
            asyncio.run(self._async_start())
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

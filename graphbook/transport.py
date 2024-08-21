import pickle
from typing import Tuple
import traceback
from asyncio.streams import StreamReader, StreamWriter
import asyncio


class NetworkService:
    def __init__(self, host, port, routes):
        self.host = host
        self.port = port
        self.routes = routes

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
                for route in self.routes:
                    if route["header"] == header:
                        route["handler"](payload)
                        break
                    elif route["header"] == "OK":
                        self.handle_ok()
                        writer.write("OK\n".encode())
                else:
                    print("Unknown header", header)

        writer.close()

    async def start(self):
        server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )

        addr = server.sockets[0].getsockname()
        print(f"Serving on {addr}")

        async with server:
            await server.serve_forever()
            
class NetworkClient:
    DefaultPort = 8008
    def __init__(self, host, port=DefaultPort):
        self.host = host
        self.port = port
        self.reader, self.writer = None, None
        
    async def connect(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        self.reader, self.writer = reader, writer
        
    def close(self):
        self.writer.close()

    def send(self, header: str, payload: any):
        header = header + "\n"
        header = header.encode()
        self.writer.write(header)
        payload = pickle.dumps(payload)
        payload_len = len(payload)
        payload_len = f"{payload_len}\n".encode()
        self.writer.write(payload_len)
        self.writer.write(payload)

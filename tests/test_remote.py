import asyncio
import pickle
import pytest
import torch
from graphbook import Note
from graphbook.utils import send_remote_packet


@pytest.mark.asyncio
async def test_conn():
    async def receive_ok_response():
        res = await reader.readuntil()
        res = res.decode().strip()
        assert res == "OK"

    reader, writer = await asyncio.open_connection("localhost", 8008)
    await send_remote_packet(writer, "OK")
    await send_remote_packet(writer, "OK")
    await send_remote_packet(writer, "OK")
    await send_remote_packet(writer, "OK")
    await receive_ok_response()
    await receive_ok_response()
    await receive_ok_response()
    await receive_ok_response()
    writer.close()


@pytest.mark.asyncio
async def test_tensor_payload():
    reader, writer = await asyncio.open_connection("localhost", 8008)
    t = torch.tensor([1, 2, 3], requires_grad=False)
    note = Note({"tensor": t})
    buf = pickle.dumps(note)
    writer.write(b"NOTE\n")
    writer.write(f"{len(buf)}\n".encode())
    writer.write(buf)
    await writer.drain()

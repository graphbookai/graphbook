import aiohttp.web as web
import ray
import queue
from .ray_processor import RayStepHandler
from typing import Optional
import asyncio
import uuid
import multiprocessing as mp
from graphbook.core.clients import Client
from graphbook.core.viewer import MultiGraphViewManager
from graphbook.core.clients import ClientPool
from aiohttp.web import WebSocketResponse


class RayProcessorInterface:
    def __init__(self, processor: RayStepHandler, proc_queue: queue.Queue):
        self.processor = processor
        self.queue = proc_queue

    def get_output(self, step_id: str, pin_id: str, index: int):
        return ray.get(self.processor.get_output.remote(step_id, pin_id, index))

    def pause(self):
        raise NotImplementedError("RayProcessor does not support pause")

    def get_queue(self):
        return self.queue


class RayClient(Client):
    def __init__(
        self,
        sid: str,
        ws: web.WebSocketResponse,
        view_manager: MultiGraphViewManager,
        proc_queue: queue.Queue,
    ):
        processor = ray.get_actor("_graphbook_RayStepHandler")
        self.processor_interface = RayProcessorInterface(processor, proc_queue)
        super().__init__(sid, ws, view_manager, self.processor_interface)

    def get_processor(self) -> RayProcessorInterface:
        return self.processor_interface


class RayClientPool(ClientPool):
    def __init__(
        self,
        close_event: mp.Event,
        proc_queue: Optional[mp.Queue] = None,
        view_queue: Optional[mp.Queue] = None,
    ):
        super().__init__(close_event,)
        self.proc_queue = proc_queue
        self.view_queue = view_queue
        self.view_manager = MultiGraphViewManager(
            view_queue, close_event=self.close_event
        )

    async def add_client(self, ws: WebSocketResponse) -> Client:
        sid = uuid.uuid4().hex

        client = RayClient(
            sid, ws, view_manager=self.view_manager, proc_queue=self.proc_queue
        )
        print(f"{sid}: (Ray client)")
        self.clients[sid] = client
        self.ws[sid] = ws
        await ws.send_json({"type": "sid", "data": sid})
        return client

    async def loop(self):
        view_manager: MultiGraphViewManager = self.view_manager
        view_data = view_manager.get_current_view_data()
        for client in list(self.clients.values()):
            if client.ws.closed:
                continue
            state_data = self.get_state_data(view_manager, client)
            try:
                await asyncio.gather(
                    *[client.ws.send_json(data) for data in [*view_data, *state_data]]
                )
            except Exception as e:
                print(f"Error sending to client: {e}")

    def start(self):
        super().start()
        self.view_manager.start()

    async def stop(self):
        await super().stop()
        self.view_manager.stop()

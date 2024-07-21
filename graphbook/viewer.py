from typing import Dict, List
import magic
import os.path as osp
from aiohttp.web import WebSocketResponse
import uuid
import asyncio
import time
import multiprocessing as mp
import queue
import copy
import psutil
from graphbook.utils import MP_WORKER_TIMEOUT, get_gpu_util


class Viewer:
    def __init__(self, event_name: str):
        self.event_name = event_name

    def get_event_name(self):
        return self.event_name

    def handle_outputs(self, node_id: str, outputs: dict):
        pass

    def handle_start(self, node_id: str):
        pass

    def handle_end(self):
        pass

    def get_next(self):
        return None


"""
This class is used to store the data records that are generated by the steps in the pipeline
and provides a way to access them by node_id and index, so that the data can be displayed in
the web interface. We will only store a fixed amount of records at a time by implementing a
sliding window using a double-ended queue per step node.
"""


class DataViewer(Viewer):
    def __init__(self, deque_max_size=5):
        super().__init__("view")
        self.deque_max_size = deque_max_size
        self.last_outputs: Dict[str, dict] = {}

    def handle_outputs(self, node_id: str, output: dict):
        if node_id not in self.last_outputs:
            self.last_outputs[node_id] = {}
        new_entries = {k: v[0].items for k, v in output.items() if len(v) > 0}
        self.last_outputs[node_id] |= new_entries

    def get_next(self):
        return self.last_outputs


"""
NodeStatsViewer (for tracking stats of the pipeline, e.g. time taken per step, memory usage, queue sizes.)
"""


class NodeStatsViewer(Viewer):
    def __init__(self):
        super().__init__("stats")
        self.queue_sizes: Dict[str, dict] = {}
        self.record_rate: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}
        self.execution_times: Dict[str, float] = {}
        self.total_execution_time: float = 0

    def handle_start(self, node_id: str):
        self.start_times[node_id] = time.time()

    def handle_end(self):
        self.start_times = {}

    def handle_queue_size(self, node_id: str, sizes: dict):
        self.queue_sizes[node_id] = sizes

    def get_total_queue_size(self, node_id: str):
        return sum(self.queue_sizes[node_id].values())

    def handle_outputs(self, node_id: str, outputs: dict):
        if node_id not in self.start_times:
            return
        self.record_rate[node_id] = self.get_total_queue_size(node_id) / (
            time.time() - self.start_times[node_id]
        )

    def handle_time(self, node_id: str, time: float):
        self.total_execution_time += time
        self.execution_times[node_id] = self.execution_times.get(node_id, 0) + time

    def get_next(self):
        data_obj = {}
        for node_id in self.record_rate:
            data_obj[node_id] = {
                "record_rate": self.record_rate[node_id],
            }
        for node_id in self.queue_sizes:
            data_obj.setdefault(node_id, {})
            data_obj[node_id]["queue_size"] = self.queue_sizes[node_id]
        for node_id in self.execution_times:
            data_obj.setdefault(node_id, {})
            if self.total_execution_time > 0:
                data_obj[node_id]["execution"] = (
                    self.execution_times[node_id] / self.total_execution_time
                )
        return data_obj


"""
Updates client with new set of incoming logs
"""


class NodeLogsViewer(Viewer):
    def __init__(self):
        super().__init__("logs")
        self.logs: Dict[str, List[str]] = {}

    def handle_start(self, node_id: str):
        if node_id not in self.logs:
            self.logs[node_id] = []
        self.logs[node_id].append({"type": "wipe"})

    def handle_log(self, node_id: str, log: str, type: str = "info"):
        if node_id not in self.logs:
            self.logs[node_id] = []
        self.logs[node_id].append({"type": type, "msg": log})

    def get_next(self):
        logs = copy.deepcopy(self.logs)
        self.logs = {}
        return logs


"""
Tracks system utilization: CPU util, CPU memory, GPU util, GPU memory
"""


class SystemUtilViewer(Viewer):
    def __init__(self):
        super().__init__("system_util")

    def get_cpu_usage(self):
        return psutil.cpu_percent()

    def get_mem_usage(self):
        return psutil.virtual_memory().percent

    def get_gpu_usage(self):
        gpus = get_gpu_util()
        return gpus

    def get_next(self):
        return {
            "cpu": self.get_cpu_usage(),
            "mem": self.get_mem_usage(),
            "gpu": self.get_gpu_usage(),
        }


DEFAULT_CLIENT_OPTIONS = {"SEND_EVERY": 0.5}


class Client:
    def __init__(
        self,
        ws: WebSocketResponse,
        producers: List[DataViewer],
        options: dict = DEFAULT_CLIENT_OPTIONS,
    ):
        self.ws = ws
        self.producers = producers
        self.options = options
        self.curr_task = None

    async def _loop(self):
        while True:
            await asyncio.sleep(self.options["SEND_EVERY"])
            sends = []
            for producer in self.producers:
                next_entry = producer.get_next()
                if next_entry is not None:
                    entry = {"type": producer.get_event_name(), "data": next_entry}
                    sends.append(self.ws.send_json(entry))
            await asyncio.gather(*sends)

    def start(self):
        loop = asyncio.get_event_loop()
        self.curr_task = loop.create_task(self._loop())

    async def close(self):
        if self.curr_task is not None:
            self.curr_task.cancel()
        await self.ws.close()


class ViewManager:
    def __init__(self, work_queue: mp.Queue, close_event: mp.Event):
        self.data_viewer = DataViewer()
        self.node_stats_viewer = NodeStatsViewer()
        self.logs_viewer = NodeLogsViewer()
        self.system_util_viewer = SystemUtilViewer()
        self.viewers: List[Viewer] = [
            self.data_viewer,
            self.node_stats_viewer,
            self.logs_viewer,
            self.system_util_viewer,
        ]
        self.clients: Dict[str, Client] = {}
        self.work_queue = work_queue
        self.close_event = close_event
        self.curr_task = None

    def add_client(self, ws: WebSocketResponse) -> str:
        sid = uuid.uuid4().hex
        client = Client(ws, self.viewers)
        self.clients[sid] = client
        client.start()
        print(f"Added new client {sid}")
        return sid

    async def remove_client(self, sid: str):
        if sid in self.clients:
            print(f"Removing client {sid}")
            await self.clients[sid].close()
            del self.clients[sid]

    def close_all(self):
        for sid in self.clients:
            self.clients[sid].close()
        self.clients = {}

    def handle_outputs(self, node_id: str, outputs: dict):
        if len(outputs) == 0:
            return
        for viewer in self.viewers:
            viewer.handle_outputs(node_id, outputs)

    def handle_time(self, node_id: str, time: float):
        self.node_stats_viewer.handle_time(node_id, time)

    def handle_queue_size(self, node_id: str, size: int):
        self.node_stats_viewer.handle_queue_size(node_id, size)

    def handle_start(self, node_id: str):
        for viewer in self.viewers:
            viewer.handle_start(node_id)

    def handle_log(self, node_id: str, log: str, type: str):
        self.logs_viewer.handle_log(node_id, log, type)

    def handle_end(self):
        for viewer in self.viewers:
            viewer.handle_end()

    def send_to_clients(self, type: str, data: dict):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sends = []
        for client in self.clients.values():
            entry = {"type": type} | data
            sends.append(client.ws.send_json(entry))
        loop.run_until_complete(asyncio.gather(*sends))
        loop.close()

    def handle_run_state(self, is_running: bool):
        self.send_to_clients("run_state", {"is_running": is_running})

    def _loop(self):
        while not self.close_event.is_set():
            try:
                work = self.work_queue.get(timeout=MP_WORKER_TIMEOUT)
                if work["cmd"] == "handle_outputs":
                    self.handle_outputs(work["node_id"], work["outputs"])
                elif work["cmd"] == "handle_queue_size":
                    self.handle_queue_size(work["node_id"], work["size"])
                elif work["cmd"] == "handle_time":
                    self.handle_time(work["node_id"], work["time"])
                elif work["cmd"] == "handle_start":
                    self.handle_start(work["node_id"])
                elif work["cmd"] == "handle_end":
                    self.handle_end()
                elif work["cmd"] == "handle_log":
                    self.handle_log(work["node_id"], work["log"], work["type"])
                elif work["cmd"] == "handle_run_state":
                    self.handle_run_state(work["is_running"])
            except queue.Empty:
                pass

    def start(self):
        self._loop()

    async def close(self):
        if self.curr_task is not None:
            self.curr_task.cancel()
        await asyncio.gather(*[client.close() for client in self.clients.values()])


class ViewManagerInterface:
    def __init__(self, view_manager_queue: mp.Queue):
        self.view_manager_queue = view_manager_queue

    def handle_log(self, node_id: str, log: str, type: str = "info"):
        self.view_manager_queue.put(
            {"cmd": "handle_log", "node_id": node_id, "log": log, "type": type}
        )

    def handle_outputs(self, node_id: str, outputs: dict):
        if len(outputs) == 0:
            return
        self.view_manager_queue.put(
            {"cmd": "handle_outputs", "node_id": node_id, "outputs": outputs}
        )

    def handle_time(self, node_id: str, time: float):
        self.view_manager_queue.put(
            {"cmd": "handle_time", "node_id": node_id, "time": time}
        )

    def handle_queue_size(self, node_id: str, size: dict):
        self.view_manager_queue.put(
            {"cmd": "handle_queue_size", "node_id": node_id, "size": size}
        )

    def handle_start(self, node_id: str):
        self.view_manager_queue.put({"cmd": "handle_start", "node_id": node_id})

    def handle_end(self):
        self.view_manager_queue.put({"cmd": "handle_end"})

    def handle_run_state(self, is_running: bool):
        self.view_manager_queue.put(
            {"cmd": "handle_run_state", "is_running": is_running}
        )


class Logger:
    def __init__(self, view_manager_queue: mp.Queue, node_id: str, node_name: str):
        self.view_manager = ViewManagerInterface(view_manager_queue)
        self.node_id = node_id
        self.node_name = node_name

    def log(self, msg: str):
        print(f"[{self.node_id} {self.node_name}] {msg}")
        self.view_manager.handle_log(self.node_id, msg)

    def log_exception(self, e: Exception):
        self.view_manager.handle_log(self.node_id, "[ERR] " + str(e), type="error")

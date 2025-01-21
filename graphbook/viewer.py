from typing import Dict, List, Any, Tuple, Optional, TYPE_CHECKING
import asyncio
import time
import multiprocessing as mp
import queue
import copy
import psutil
from .utils import MP_WORKER_TIMEOUT, get_gpu_util
import ray.util.queue

if TYPE_CHECKING:
    from .processing.web_processor import WebInstanceProcessor


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

    def handle_clear(self, node_id: str):
        pass

    def get_next(self):
        return None


class DataViewer(Viewer):
    """
    This class is used to store the a preview of the notes that are generated by the steps in the pipeline
    so that the data can be displayed in the web interface.
    """

    def __init__(self):
        super().__init__("view")
        self.last_outputs: Dict[str, dict] = {}
        self.filename = None

    def handle_outputs(self, node_id: str, output: dict):
        if node_id not in self.last_outputs:
            self.last_outputs[node_id] = {}
        new_entries = {k: v[-1] for k, v in output.items() if len(v) > 0}
        self.last_outputs[node_id] |= new_entries

    def set_filename(self, filename: str):
        if filename != self.filename:
            self.filename = filename
            self.last_outputs = {}

    def handle_clear(self, node_id: str | None = None):
        if node_id is None:
            self.last_outputs = {}
        if node_id in self.last_outputs:
            del self.last_outputs[node_id]

    def get_next(self):
        return self.last_outputs


class NodeStatsViewer(Viewer):
    """
    NodeStatsViewer (for tracking stats of the pipeline, e.g. time taken per step, memory usage, queue sizes.)
    """

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


class NodeLogsViewer(Viewer):
    """
    Updates client with new set of incoming logs
    """

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


class SystemUtilViewer(Viewer):
    """
    Tracks system utilization: CPU util, CPU memory, GPU util, GPU memory
    """

    def __init__(self, processor: Optional["WebInstanceProcessor"] = None):
        super().__init__("system_util")
        self.processor = processor

    def get_cpu_usage(self):
        return psutil.cpu_percent()

    def get_mem_usage(self):
        return psutil.virtual_memory().percent

    def get_gpu_usage(self):
        gpus = get_gpu_util()
        return gpus

    def get_next(self):
        sizes = {}
        if self.processor:
            sizes = self.processor.get_worker_queue_sizes()
        return {
            "cpu": self.get_cpu_usage(),
            "mem": self.get_mem_usage(),
            "gpu": self.get_gpu_usage(),
            "worker_queue_sizes": sizes,
        }


class PromptViewer(Viewer):
    def __init__(self):
        super().__init__("prompt")
        self.prompts = {}

    def handle_prompt(self, node_id: str, prompt: dict):
        prev_prompt = self.prompts.get(node_id)
        idx = 0
        if prev_prompt:
            idx = prev_prompt["idx"] + 1
        prompt["idx"] = idx
        self.prompts[node_id] = prompt

    def get_next(self):
        return self.prompts


StateEntry = Tuple[int, dict]


class MultiGraphViewManager:
    def __init__(
        self,
        work_queue: mp.Queue,
        processor: Optional["WebInstanceProcessor"] = None,
    ):
        self.system_util_viewer = SystemUtilViewer(processor)
        self.node_stats_viewers: Dict[str, NodeStatsViewer] = {}
        self.log_viewers: Dict[str, NodeLogsViewer] = {}
        self.prompt_viewers: Dict[str, PromptViewer] = {}
        self.viewers: Dict[str, List[Viewer]] = {}
        self.graph_states: Dict[str, Dict[str, StateEntry]] = {}
        self.work_queue = work_queue
        self.close_event = mp.Event()

    def get_viewers(self, graph_id: str):
        return self.viewers[graph_id]

    def handle_new_graph(self, graph_id: str):
        self.node_stats_viewers[graph_id] = NodeStatsViewer()
        self.log_viewers[graph_id] = NodeLogsViewer()
        self.prompt_viewers[graph_id] = PromptViewer()
        self.viewers[graph_id] = [
            self.node_stats_viewers[graph_id],
            self.log_viewers[graph_id],
            self.prompt_viewers[graph_id],
            DataViewer(),
        ]
        self.graph_states[graph_id] = {}

    def rm_graph(self, graph_id: str):
        del self.viewers[graph_id]
        del self.graph_states[graph_id]

    def handle_outputs(self, graph_id: str, node_id: str, outputs: dict):
        if len(outputs) == 0:
            return
        if graph_id not in self.viewers:
            return
        for viewer in self.viewers[graph_id]:
            viewer.handle_outputs(node_id, outputs)

    def handle_time(self, graph_id: str, node_id: str, time: float):
        if graph_id not in self.viewers:
            return
        self.node_stats_viewers[graph_id].handle_time(node_id, time)

    def handle_queue_size(self, graph_id: str, node_id: str, size: int):
        self.node_stats_viewers[graph_id].handle_queue_size(node_id, size)

    def handle_start(self, graph_id: str, node_id: str):
        if graph_id not in self.viewers:
            return
        for viewer in self.viewers[graph_id]:
            viewer.handle_start(node_id)

    def handle_clear(self, graph_id: str, node_id: str | None):
        if graph_id not in self.viewers:
            return
        for viewer in self.viewers[graph_id]:
            viewer.handle_clear(node_id)

    def handle_log(self, graph_id: str, node_id: str, log: str, type: str):
        self.log_viewers[graph_id].handle_log(node_id, log, type)

    def handle_prompt(self, graph_id: str, node_id: str, prompt: dict):
        self.prompt_viewers[graph_id].handle_prompt(node_id, prompt)

    def handle_end(self, graph_id: str):
        if graph_id not in self.viewers:
            return
        for viewer in self.viewers[graph_id]:
            viewer.handle_end()

    def set_state(self, graph_id: str, type: str, data: Any = None):
        """
        Set state data for a specific type
        """
        states = self.graph_states.get(graph_id, None)
        if states is None:
            return
        original = states.get(type, None)
        if original is not None:
            i, _ = original
            states[type] = (i + 1, data)
            return
        states[type] = (0, data)

    def get_current_states(self, client_idx: dict) -> List[StateEntry]:
        """
        Retrieve all current state data
        """
        states = [
            (
                state_entry[0],
                {"graph_id": graph_id, "type": state_type, "data": state_entry[1]},
            )
            for graph_id, states in self.graph_states.items()
            for state_type, state_entry in states.items()
            if graph_id not in client_idx
            or state_type not in client_idx[graph_id]
            or state_entry[0] > client_idx[graph_id][state_type]
        ]
        return states

    def get_current_view_data(self) -> List[dict]:
        """
        Get the current data from all viewer classes
        """
        view_data = []
        for graph_id, viewers in self.viewers.items():
            for viewer in viewers:
                next_entry = viewer.get_next()
                if next_entry is not None:
                    entry = {
                        "graph_id": graph_id,
                        "type": viewer.get_event_name(),
                        "data": next_entry,
                    }
                    view_data.append(entry)
        view_data.append(
            {"type": "system_util", "data": self.system_util_viewer.get_next()}
        )
        return view_data

    def _loop(self):
        try:
            while not self.close_event.is_set():
                try:
                    work = self.work_queue.get(timeout=MP_WORKER_TIMEOUT)
                    if work.get("cmd") is None or work.get("graph_id") is None:
                        print("MultiGraphViewManager: Received invalid work:", work)
                        continue
                    if work["cmd"] == "handle_new_graph":
                        self.handle_new_graph(work["graph_id"])
                    elif work["cmd"] == "handle_outputs":
                        self.handle_outputs(
                            work["graph_id"], work["node_id"], work["outputs"]
                        )
                    elif work["cmd"] == "handle_queue_size":
                        self.handle_queue_size(
                            work["graph_id"], work["node_id"], work["size"]
                        )
                    elif work["cmd"] == "handle_time":
                        self.handle_time(
                            work["graph_id"], work["node_id"], work["time"]
                        )
                    elif work["cmd"] == "handle_start":
                        self.handle_start(work["graph_id"], work["node_id"])
                    elif work["cmd"] == "handle_end":
                        self.handle_end(work["graph_id"])
                    elif work["cmd"] == "handle_log":
                        self.handle_log(
                            work["graph_id"], work["node_id"], work["log"], work["type"]
                        )
                    elif work["cmd"] == "handle_clear":
                        self.handle_clear(work["graph_id"], work["node_id"])
                    elif work["cmd"] == "handle_prompt":
                        self.handle_prompt(
                            work["graph_id"], work["node_id"], work["prompt"]
                        )
                    elif work["cmd"] == "set_state":
                        self.set_state(work["graph_id"], work["type"], work["data"])
                    else:
                        print(
                            "MultiGraphViewManager: Received invalid work cmd:",
                            work["cmd"],
                        )
                except queue.Empty:
                    pass
                except ray.util.queue.Empty:
                    pass
                except asyncio.exceptions.CancelledError:
                    self.close_event.set()
                    break
        except Exception as e:
            print(f"MultiGraphViewManager Error: {e}")
            raise

    def start(self):
        loop = asyncio.new_event_loop()
        loop.run_in_executor(None, self._loop)

    def stop(self):
        self.close_event.set()


class ViewManagerInterface:
    def __init__(self, graph_id: str, queue: mp.Queue):
        self.graph_id = graph_id
        self.queue = queue
        self.handle_new_graph()

    def handle_new_graph(self):
        self.queue.put({"cmd": "handle_new_graph", "graph_id": self.graph_id})

    def handle_outputs(self, node_id: str, outputs: dict):
        if len(outputs) == 0:
            return
        self.queue.put(
            {
                "cmd": "handle_outputs",
                "graph_id": self.graph_id,
                "node_id": node_id,
                "outputs": outputs,
            }
        )

    def handle_time(self, node_id: str, time: float):
        self.queue.put(
            {
                "cmd": "handle_time",
                "graph_id": self.graph_id,
                "node_id": node_id,
                "time": time,
            }
        )

    def handle_start(self, node_id: str):
        self.queue.put(
            {"cmd": "handle_start", "graph_id": self.graph_id, "node_id": node_id}
        )

    def handle_end(self):
        self.queue.put(
            {
                "cmd": "handle_end",
                "graph_id": self.graph_id,
            }
        )

    def handle_clear(self, node_id: str | None):
        self.queue.put(
            {"cmd": "handle_clear", "graph_id": self.graph_id, "node_id": node_id}
        )

    def set_state(self, type: str, data: Any):
        self.queue.put(
            {"cmd": "set_state", "graph_id": self.graph_id, "type": type, "data": data}
        )

    def handle_queue_size(self, node_id: str, size: dict):
        self.queue.put(
            {
                "cmd": "handle_queue_size",
                "graph_id": self.graph_id,
                "node_id": node_id,
                "size": size,
            }
        )

    def handle_log(self, node_id: str, log: str, type: str = "info"):
        self.queue.put(
            {
                "cmd": "handle_log",
                "graph_id": self.graph_id,
                "node_id": node_id,
                "log": log,
                "type": type,
            }
        )

    def handle_prompt(self, node_id: str, prompt: dict):
        self.queue.put(
            {
                "cmd": "handle_prompt",
                "graph_id": self.graph_id,
                "node_id": node_id,
                "prompt": prompt,
            }
        )


class MultiGraphViewManagerInterface:
    def __init__(self, view_manager_queue: mp.Queue):
        self.view_manager_queue = view_manager_queue

    def new(self, graph_id: str):
        return ViewManagerInterface(graph_id, self.view_manager_queue)

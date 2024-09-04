import multiprocessing as mp
from typing import Dict, Tuple
import inspect
from graphbook.viewer import ViewManagerInterface
from torch import Tensor
from numpy import ndarray

logging_nodes = None
view_manager = None
text_log_types = ["info", "error"]


def setup_logging_nodes(nodes: Dict[int, Tuple[str, str]], queue: mp.Queue):
    global logging_nodes
    global view_manager
    logging_nodes = nodes
    view_manager = ViewManagerInterface(queue)


def transform_json_log(log: any):
    if isinstance(log, dict):
        return {k: transform_json_log(v) for k, v in log.items()}
    if isinstance(log, list):
        return [transform_json_log(v) for v in log]
    if isinstance(log, tuple):
        return [transform_json_log(v) for v in log]
    if isinstance(log, set):
        return [transform_json_log(v) for v in log]
    if isinstance(log, Tensor):
        return f"tensor of shape {log.shape}"
    if isinstance(log, ndarray):
        return f"ndarray of shape {log.shape}"
    return log


def log(msg: str, type: str = "info", caller_id: int | None = None):
    if caller_id is None:
        prev_frame = inspect.currentframe().f_back
        caller = prev_frame.f_locals.get("self")
        if caller is not None:
            caller_id = id(caller)

    node = logging_nodes.get(caller_id, None)
    if node is None:
        raise ValueError(
            f"Can't find node id in {caller}. Only initialized steps can log."
        )
    node_id, node_name = node

    if type in text_log_types:
        if type == "error":
            msg = f"[ERR] {msg}"
        print(f"[{node_id} {node_name}] {msg}")
    else:
        msg = transform_json_log(msg)
    view_manager.handle_log(node_id, msg, type)

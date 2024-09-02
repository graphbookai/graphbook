import multiprocessing as mp
from typing import Dict, Tuple
import inspect
from graphbook.viewer import ViewManagerInterface

logging_nodes = None
view_manager = None


def setup_logging_nodes(nodes: Dict[int, Tuple[str, str]], queue: mp.Queue):
    global logging_nodes
    global view_manager
    logging_nodes = nodes
    view_manager = ViewManagerInterface(queue)


def log(msg: str, type: str = "info", caller_id: int | None = None):
    if caller_id is None:
        prev_frame = inspect.currentframe().f_back
        # class = prev_frame.f_locals['self'].__class__()
        caller = prev_frame.f_locals.get("self")
        if caller is not None:
            caller_id = id(caller)

    node = logging_nodes.get(caller_id, None)
    if node is None:
        raise ValueError(
            f"Can't find node id in {caller}. Only initialized steps can log."
        )
    node_id, node_name = node
    if type == "error":
        msg = f"[ERR] {msg}"
    msg = f"[{node_id} {node_name}] {msg}"
    print(msg)
    view_manager.handle_log(node_id, msg, type)

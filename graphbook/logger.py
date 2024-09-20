from typing import Literal
import multiprocessing as mp
from typing import Dict, Tuple, Any
import inspect
from graphbook.note import Note
from graphbook.viewer import ViewManagerInterface
from graphbook.utils import transform_json_log

logging_nodes = None
view_manager = None
text_log_types = ["info", "error"]

LogType = Literal["info", "error", "json", "image"]


def setup_logging_nodes(nodes: Dict[int, Tuple[str, str]], queue: mp.Queue):
    global logging_nodes
    global view_manager
    logging_nodes = nodes
    view_manager = ViewManagerInterface(queue)


def log(msg: Any, type: LogType = "info", caller_id: int | None = None):
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
    elif type == "json":
        msg = transform_json_log(msg)
    elif type == "image":
        pass # TODO
    else:
        raise ValueError(f"Unknown log type {type}")
    view_manager.handle_log(node_id, msg, type)
    
def prompt(prompt: dict, caller_id: int | None = None):
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
    node_id, _ = node
    view_manager.handle_prompt(node_id, prompt)

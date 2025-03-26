from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Generator,
    List,
    Tuple,
    Any,
)
import logging
import ray
import ray._raylet
from ray.actor import ActorHandle
from ray.util import queue
from ray.dag import DAGNode
from ray.dag.class_node import ClassMethodNode
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from PIL import Image
from graphbook.core.viewer import MultiGraphViewManagerInterface, ViewManagerInterface
from graphbook.core.processing.event_handler import FileEventHandler
from graphbook.core.steps import Step, StepOutput
from graphbook.core.utils import MP_WORKER_TIMEOUT, transform_json_log
import ray.util.queue


logger = logging.getLogger(__name__)

step_output_err_res = "Step output must be a dictionary, and dict values must be lists."


@dataclass
class GraphbookTaskContext:
    """
    The structure for saving workflow task context. The context provides
    critical info (e.g. where to checkpoint, which is its parent task)
    for the task to execute correctly.
    """

    # ID of the workflow.
    name: Optional[str] = None
    # ID of the current task.
    task_id: str = ""


_context: Optional[GraphbookTaskContext] = None


@contextmanager
def graphbook_task_context(context) -> Generator[None, None, None]:
    """Initialize the workflow task context.

    Args:
        context: The new context.
    """
    global _context
    original_context = _context
    try:
        _context = context
        yield
    finally:
        _context = original_context


@ray.remote(name="_graphbook_RayStepHandler")
class RayStepHandler:
    def __init__(self, cmd_queue: queue.Queue, view_manager_queue: queue.Queue):
        self.view_manager_queue = view_manager_queue
        self.event_handler = None
        self.viewer = None
        self.graph_state = RayExecutionState()
        self.cmd_queue = cmd_queue
        self.log_dir = "logs"

    def handle_new_execution(
        self, name: str, G: dict, log_dir: str = "logs", wait_for_params=True
    ):
        # Store the log directory
        self.log_dir = log_dir

        # Create a new event handler
        self.event_handler = FileEventHandler(
            name, self.view_manager_queue, self.log_dir
        )

        # Initialize the viewer
        self.graph_state.set_viewer(self.viewer)

        # Update metadata
        self.event_handler.update_metadata({"graph": G})

        if wait_for_params:
            params = self.wait_for_params()
            return params

    def handle_start_execution(self):
        # Use event handler to update the state
        self.event_handler.viewer.set_state("run_state", "running")

    def handle_end_execution(self, *outputs):
        # Mark execution as finished
        self.event_handler.handle_end()
        # Clean up resources
        self.event_handler.cleanup()
        return outputs

    def handle_log(self, node_id, msg, type):
        self.event_handler.write_log(node_id, msg, type)

    def prepare_inputs(
        self, dummy_input, step_id: str, *bind_args: List[Tuple[str, dict]]
    ) -> Optional[List[Any]]:
        all_datas = []
        for i in range(0, len(bind_args), 2):
            bind_key, outputs = bind_args[i], bind_args[i + 1]
            datas = outputs.get(bind_key)
            if datas is None:
                raise ValueError(f"[{step_id}] Couldn't get outputs at {bind_key}")
            all_datas.extend(outputs[bind_key])
        return all_datas

    def handle_outputs(self, step_id: str, outputs: StepOutput):
        # Use event handler to write outputs and handle events

        # Process images for Ray
        self.graph_state.handle_images(outputs)

        # Log step output to file
        for pin_id, output_list in outputs.items():
            for output in output_list:
                self.event_handler.write_output(step_id, pin_id, output)

        return outputs

    def get_output(self, step_id, pin_id, index):
        # Try to get output using event handler if available
        if self.event_handler and hasattr(self.event_handler, "get_output"):
            return self.event_handler.get_output(step_id, pin_id, index)

        # Fall back to graph state
        if (
            step_id in self.graph_state.steps_outputs
            and pin_id in self.graph_state.steps_outputs[step_id]
        ):
            return {
                "step_id": step_id,
                "pin_id": pin_id,
                "index": index,
                "data": transform_json_log(
                    self.graph_state.steps_outputs[step_id][pin_id][index]
                ),
            }

        return None

    def get_image(self, image_id: str):
        return self.graph_state.get_image(image_id)

    def wait_for_params(self) -> dict:
        def _loop():
            while True:
                try:
                    work = self.cmd_queue.get(timeout=MP_WORKER_TIMEOUT)
                    if work["cmd"] == "set_params":
                        self.graph_state.set_params(work.get("params"))
                        return work.get("params")
                except queue.Empty:
                    pass
                except KeyboardInterrupt:
                    print("KeyboardInterrupt in RayInterface")
                    break
                except Exception as e:
                    print("Error in RayInterface:", e)
                    break
            return None

        return _loop()


class RayExecutionState:
    def __init__(self):
        self.viewer = None
        self.curr_idx = 0
        self.steps_outputs: Dict[str, DictionaryArrays] = {}
        self.handled_steps = set()
        self.params = None
        self.images: Dict[str, ray._raylet.ObjectRef] = {}
        self.event_handler = None

    def set_viewer(self, viewer: ViewManagerInterface):
        self.viewer = viewer

    def set_params(self, params):
        self.params = params

    def get_iterator(self, step_id: str, label: str):
        for data in self.steps_outputs[step_id][label]:
            yield data

    def handle_images(self, outputs: StepOutput):
        def try_add_image(item):
            if isinstance(item, dict):
                if item.get("shm_id") is not None:
                    return
                if item.get("type") == "image" and isinstance(
                    item.get("value"), Image.Image
                ):
                    obj_ref = ray.put(item["value"])
                    shm_id = str(obj_ref)
                    self.images[shm_id] = obj_ref
                    item["shm_id"] = shm_id
            elif isinstance(item, list):
                for val in item:
                    try_add_image(val)

        for output in outputs.values():
            for data in output:
                if not isinstance(data, dict):
                    continue
                for item in data.values():
                    if isinstance(item, list):
                        for i in item:
                            try_add_image(i)
                    else:
                        try_add_image(item)

    def get_image(self, image_id: str):
        return ray.get(self.images.get(image_id, None))

    def handle_outputs(self, step_id: str, outputs: StepOutput):
        assert self.viewer is not None, "Viewer not initialized"
        if step_id in self.handled_steps:
            return

        self.handled_steps.add(step_id)
        if not step_id in self.steps_outputs:
            self.steps_outputs[step_id] = DictionaryArrays()
        for label, datas in outputs.items():
            self.steps_outputs[step_id].enqueue(label, datas)

        # Use viewer for UI updates
        self.viewer.handle_queue_size(step_id, self.steps_outputs[step_id].sizes())
        for pin, output in outputs.items():
            if len(output) == 0:
                continue

            self.viewer.handle_output(step_id, pin, transform_json_log(output[-1]))


class DictionaryArrays:
    def __init__(self):
        self._dict: Dict[str, list] = {}

    def enqueue(self, label: str, outputs: List[Any]):
        if label not in self._dict:
            self._dict[label] = []
        self._dict[label].extend(outputs)

    def __getitem__(self, label: str):
        return self._dict[label]

    def sizes(self):
        return {k: len(v) for k, v in self._dict.items()}

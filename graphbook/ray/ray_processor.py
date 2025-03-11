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
import traceback
from graphbook.core.viewer import MultiGraphViewManagerInterface, ViewManagerInterface
from graphbook.core.steps import Step, StepOutput
from graphbook.core.utils import MP_WORKER_TIMEOUT, transform_json_log
from graphbook.core.processing.graph_processor import Executor
from graphbook.core.serialization import Graph
from .ray_img import RayMemoryManager
from .ray_client import RayClientPool
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


def execute(dag: DAGNode, context: GraphbookTaskContext) -> None:
    """Execute a Graphbook DAG.

    Args:
        dag: A leaf node of the DAG.
        context: The execution context.
    Returns:
        An object ref that represent the result.
    """
    logger.info(f"Graphbook job [id={context.name}] started.")
    try:
        return dag.execute()
    finally:
        pass


def create_graph_execution(
    dag: DAGNode,
) -> Tuple[dict, List[Tuple[str, str, ActorHandle]]]:
    """
    Create a graph execution.

    Args:
        dag: The leaf node to the dag
    """
    # BFS

    actor_id_to_idx = {}
    nodes = []
    G = {}

    def fn(node: ClassMethodNode):
        handle: ActorHandle = node._parent_class_node
        node_context = getattr(handle, "_graphbook_context", None)
        if node_context is not None:
            curr_id = str(handle._actor_id)
            if curr_id in G:
                return

            node_id = node_context["node_id"]
            node_class = node_context["class"]
            node_name = node_class.__name__[len("ActorClass(") : -1]
            node_doc = node_context["doc"]

            if issubclass(node_class, Step):
                step_deps = node_context.get("step_deps", [])
                G[curr_id] = {
                    "type": "step",
                    "name": node_name,
                    "parameters": deepcopy(getattr(node_class, "Parameters", {})),
                    "inputs": step_deps,
                    "outputs": getattr(node_class, "Outputs", ["out"]),
                    "category": getattr(node_class, "Category", ""),
                    "doc": node_doc or "",
                }
            else:  # Resource
                G[curr_id] = {
                    "type": "resource",
                    "name": node_name,
                    "parameters": deepcopy(getattr(node_class, "Parameters", {})),
                    "category": getattr(node_class, "Category", ""),
                    "doc": node_doc or "",
                }

            resource_deps = node_context["resource_deps"]
            parameters = G[curr_id]["parameters"]
            for k, actor_id in resource_deps.items():
                parameters[k]["value"] = actor_id

            actor_id_to_idx[curr_id] = node_id
            nodes.append((node_id, node_name, handle))

    dag.traverse_and_apply(fn)

    # Transform actor ids to simple ids
    for n in G:
        if G[n]["type"] == "step":
            for input in G[n]["inputs"]:
                input["node"] = actor_id_to_idx[input["node"]]
        parameters = G[n]["parameters"]
        for k, param in parameters.items():
            if param["type"] == "resource":
                param["value"] = actor_id_to_idx[param["value"]]
    for k in list(G):
        G[actor_id_to_idx[k]] = G.pop(k)

    return G, nodes


@ray.remote(name="_graphbook_RayStepHandler")
class RayStepHandler:
    def __init__(self, cmd_queue: queue.Queue, view_manager_queue: queue.Queue):
        self.view_manager = MultiGraphViewManagerInterface(view_manager_queue)
        self.viewer = None
        self.graph_state = RayExecutionState()
        self.cmd_queue = cmd_queue

    def init_step(self):
        return self.graph_state.init_step()

    def init_resource(self):
        return self.graph_state.init_resource()

    def handle_new_execution(self, name: str, G: dict):
        self.viewer = self.view_manager.new(name)
        self.graph_state.set_viewer(self.viewer)
        self.viewer.set_state("run_state", "initializing")
        self.viewer.set_state("graph_state", G)
        params = self.wait_for_params()
        return params

    def handle_start_execution(self):
        assert self.viewer is not None
        self.viewer.set_state("run_state", "running")

    def handle_end_execution(self, outputs):
        assert self.viewer is not None
        self.viewer.set_state("run_state", "finished")
        return outputs

    def handle_log(self, node_id, msg, type):
        assert self.viewer is not None
        self.viewer.handle_log(node_id, msg, type)

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
        self.graph_state.handle_images(outputs)
        self.graph_state.handle_outputs(step_id, outputs)
        return outputs

    def get_output(self, step_id, pin_id, index):
        return {
            "step_id": step_id,
            "pin_id": pin_id,
            "index": index,
            "data": transform_json_log(
                self.graph_state.steps_outputs[step_id][pin_id][index]
            ),
        }

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

    def set_viewer(self, viewer: ViewManagerInterface):
        self.viewer = viewer

    def init_step(self):
        idx = str(self.curr_idx)
        self.curr_idx += 1
        self.steps_outputs[idx] = DictionaryArrays()
        return idx

    def init_resource(self):
        idx = str(self.curr_idx)
        self.curr_idx += 1
        return idx

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
        assert step_id in self.steps_outputs, f"Step {step_id} not initialized"
        assert self.viewer is not None, "Viewer not initialized"
        if step_id in self.handled_steps:
            return
        self.handled_steps.add(step_id)
        for label, datas in outputs.items():
            self.steps_outputs[step_id].enqueue(label, datas)

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


class RayExecutor(Executor):
    """
    Ray execution engine that runs Graphbook workflows using Ray.
    """

    def __init__(self):
        """
        Initialize the RayExecutor.

        Args:
            view_manager_queue (Optional[queue.Queue]): Queue for communicating with the view manager
            continue_on_failure (bool): Whether to continue execution after a step fails
        """
        if not ray.is_initialized():
            ray.init()

        self.cmd_queue = ray.util.queue.Queue()
        self.view_queue = ray.util.queue.Queue()

        self.client_pool = RayClientPool(
            proc_queue=self.cmd_queue,
            view_queue=self.view_queue,
        )

        # Initialize the Ray step handler
        self.handler = RayStepHandler.remote(self.cmd_queue, self.view_queue)

    def get_client_pool(self):
        return self.client_pool

    def get_img_storage(self):
        return RayMemoryManager

    def run(self, graph: Graph, step_id: Optional[str] = None):
        """
        Execute the provided graph using Ray.

        Args:
            graph (Dict[str, Any]): The serialized graph to execute
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
        """
        try:
            # Create a new execution context
            context = GraphbookTaskContext(
                name="memory_workflow",
                task_id="main",
            )

            # Initialize the execution and get the Ray dag
            dag = self._build_ray_dag(graph, step_id)

            # Execute the dag
            with graphbook_task_context(context):
                # Start the execution
                ray.get(self.handler.handle_start_execution.remote())

                # Execute the workflow
                execute(dag, context)

                # End the execution
                ray.get(self.handler.handle_end_execution.remote({}))

        except Exception as e:
            logger.error(f"Execution error: {type(e).__name__}: {str(e)}")
            traceback.print_exc()
            return None, None

    def _build_ray_dag(
        self, graph: Dict[str, Any], step_id: Optional[str] = None
    ) -> DAGNode:
        """
        Build a Ray DAG from the serialized graph.

        Args:
            graph (Dict[str, Any]): The serialized graph
            step_id (Optional[str]): If provided, only include the specified step and its dependencies

        Returns:
            DAGNode: The Ray DAG that can be executed
        """
        # In a real implementation, this would convert the graphbook graph to a Ray DAG
        # For now, we'll just return a placeholder
        # This method would need proper implementation based on ray_api.py
        raise NotImplementedError(
            "Building a Ray DAG from a serialized graph is not implemented. "
            "The actual implementation would need to translate graphbook graphs to Ray tasks."
        )

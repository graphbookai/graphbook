import ray
import time, uuid
from ray.dag import DAGNode, DAGInputData, ClassMethodNode
from ray.actor import ActorHandle
from typing import (
    Any,
    Dict,
    Optional,
    Generator,
    Union,
    Callable,
    TypeVar,
    List,
    TYPE_CHECKING,
)
from contextlib import contextmanager
from dataclasses import dataclass

import ray.util.queue
from graphbook.processing.ray_processor import RayStepHandler
from graphbook.steps import Step, SourceStep
from graphbook.utils import ExecutionContext
import graphbook.web
import multiprocessing as mp
import ray.dag.class_node as class_node
import ray.actor

from ray.workflow.common import (
    validate_user_metadata,
)

import logging

if TYPE_CHECKING:
    from graphbook.clients import ClientPool, Client

logger = logging.getLogger(__name__)
T = TypeVar("T")

step_handler: RayStepHandler = None


def _ensure_graphbook_initialized() -> None:
    if not ray.is_initialized():
        init()


def init() -> None:
    if not ray.is_initialized():
        # We should use get_temp_dir_path, but for ray client, we don't
        # have this one. We need a flag to tell whether it's a client
        # or a driver to use the right dir.
        # For now, just use $TMP/ray/workflow_data
        # workflow_dir = Path(tempfile.gettempdir()) / "ray" / "graphbook_data"
        # ray.init(storage=workflow_dir.as_uri())
        ray.init()
        view_queue = ray.util.queue.Queue()
        global step_handler
        step_handler = RayStepHandler.remote(view_queue)
        graphbook.web.async_start(False, False, "0.0.0.0", 8005, view_queue)


def is_graphbook_ray_initialized() -> bool:
    return ray.is_initialized() and step_handler is not None


def run_async(
    dag: DAGNode,
    *args,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ray.ObjectRef:
    """Run a workflow asynchronously.

    If the workflow with the given id already exists, it will be resumed.

    Args:
        name: A unique identifier that can be used to resume the
            workflow. If not specified, a random id will be generated.
        metadata: The metadata to add to the workflow. It has to be able
            to serialize to json.

    Returns:
       The running result as ray.ObjectRef.

    """
    _ensure_graphbook_initialized()
    if not isinstance(dag, DAGNode):
        raise TypeError("Input should be a DAG.")
    input_data = DAGInputData(*args, **kwargs)
    validate_user_metadata(metadata)
    metadata = metadata or {}

    if name is None:
        # Workflow ID format: {Entry workflow UUID}.{Unix time to nanoseconds}
        name = str(uuid.uuid4())

    # workflow_manager = workflow_access.get_management_actor()
    # if ray.get(workflow_manager.is_workflow_non_terminating.remote(workflow_id)):
    #     raise RuntimeError(f"Workflow '{workflow_id}' is already running or pending.")

    import inspect

    # state = workflow_state_from_dag(dag, input_data, workflow_id)
    logger.info(f'Graphbook job created. [id="{name}"].')
    context = GraphbookTaskContext(workflow_id=name)
    with graphbook_task_context(context):
        ray.get(step_handler.handle_new_execution.remote(name))


        # BFS
        curr_node = None
        curr_id = None
        actor_id_to_idx = {}
        context_setup_refs = []
        G = {}
        def fn(node: ClassMethodNode):
            print("Node:", node._parent_class_node)
            handle: ActorHandle = node._parent_class_node
            gb_class = getattr(handle, "_graphbook_class", None)
            if gb_class is not None:
                nonlocal curr_node, curr_id
                curr_node = node
                curr_id = str(handle._actor_id)
                node_id = getattr(handle, "_graphbook_step_id", None)
                assert node_id is not None
                node_name = gb_class.__name__[len("ActorClass(") : -1]
                G[curr_id] = {
                    "name": node_name,
                    "parameters": gb_class.Parameters,
                    "inputs": [],
                    "outputs": gb_class.Outputs,
                    "category": gb_class.Category,
                }
                actor_id_to_idx[curr_id] = node_id
                
                context_setup = handle.set_context.remote(
                    node_id=node_id,
                    node_name=node_name,
                )
                context_setup_refs.append(context_setup)
            else:
                # RayStepHandler.handle
                print(node._bound_args)
                for i in range(1, len(node._bound_args), 2):
                    G[curr_id]["inputs"].append({
                        "node": str(node._bound_args[i+1]._parent_class_node._actor_id),
                        "pin": node._bound_args[i],
                    })

        dag.traverse_and_apply(fn)
        for k in G:
            for v in G[k]["inputs"]:
                v["node"] = actor_id_to_idx[v["node"]]
        for k in list(G):
            G[actor_id_to_idx[k]] = G.pop(k)
            
        ray.get(context_setup_refs)
        
        
        print(G) # TODO: send to view, expect params to be filled in, stall before calling execute
        # dag.bind(step_handler.handle_end_execution.remote(name))
        # job_id = ray.get_runtime_context().get_job_id()
        return execute(dag, input_data, context)


def run(
    dag: DAGNode,
    *args,
    workflow_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Any:
    return ray.get(
        run_async(dag, *args, workflow_id=workflow_id, metadata=metadata, **kwargs)
    )


@dataclass
class GraphbookTaskContext:
    """
    The structure for saving workflow task context. The context provides
    critical info (e.g. where to checkpoint, which is its parent task)
    for the task to execute correctly.
    """

    # ID of the workflow.
    workflow_id: Optional[str] = None
    # ID of the current task.
    task_id: str = ""
    # The context of catching exceptions.
    catch_exceptions: bool = False


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


def execute(
    dag: DAGNode, dag_input: DAGInputData, context: GraphbookTaskContext
) -> None:
    """Execute a Graphbook DAG.

    Args:
        dag: A leaf node of the DAG.
        context: The execution context.
    Returns:
        An object ref that represent the result.
    """
    workflow_id = context.workflow_id
    logger.info(f"Workflow job [id={workflow_id}] started.")
    try:
        return dag.execute()
    finally:
        pass


class GraphbookActorClass:
    def __init__(self, actor: ray.actor.ActorClass):
        self._actor = actor

    def remote(self, *args, **kwargs):
        step_id = ray.get(step_handler.init_step.remote())

        actor_handle: ray.actor.ActorHandle = self._actor._remote(
            args=args, kwargs=kwargs, **self._actor._default_options
        )
        setattr(actor_handle, "_graphbook_class", self._actor.__class__)
        setattr(actor_handle, "_graphbook_step_id", step_id)

        def bind(self, *bind_args):
            assert (
                len(bind_args) % 2 == 0
            ), "Bind arguments must be pairs of bind_key and bind_obj"

            ref = step_handler.handle.bind(step_id, *bind_args)
            class_method_node = self.all.bind(ref)

            return class_method_node

        actor_handle.bind = bind.__get__(actor_handle)
        return actor_handle


class GraphbookSourceActorClass:
    def __init__(self, actor: ray.actor.ActorClass):
        self._actor = actor

    def remote(self, *args, **kwargs):
        step_id = ray.get(step_handler.init_step.remote())
        actor_handle: ray.actor.ActorHandle = self._actor._remote(
            args=args, kwargs=kwargs, **self._actor._default_options
        )

        setattr(actor_handle, "_graphbook_class", self._actor.__class__)
        setattr(actor_handle, "_graphbook_step_id", step_id)

        class_method_node = actor_handle.__call__.bind()
        return class_method_node


def remote(
    *args, **kwargs
) -> Union[
    ray.remote_function.RemoteFunction, ray.actor.ActorClass, GraphbookActorClass
]:
    actor_class = ray.remote(*args, **kwargs)
    if isinstance(actor_class, SourceStep):
        gb_actor_class = GraphbookSourceActorClass(actor_class)
    else:
        gb_actor_class = GraphbookActorClass(actor_class)
    return gb_actor_class

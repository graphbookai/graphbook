import ray
import uuid
from ray.dag import DAGNode, ClassMethodNode
from ray.actor import ActorHandle
import ray.util.queue
from typing import (
    Any,
    Optional,
    Generator,
    TypeVar,
)
from contextlib import contextmanager
from dataclasses import dataclass
from copy import deepcopy
from graphbook.processing.ray_processor import RayStepHandler
from graphbook.steps import Step, SourceStep
from graphbook.resources import Resource
from graphbook.utils import ExecutionContext
import graphbook.web
import ray.actor
import logging


logger = logging.getLogger(__name__)
T = TypeVar("T")
step_handler: RayStepHandler = None


def _ensure_graphbook_initialized() -> None:
    if not is_graphbook_ray_initialized():
        init()


def init() -> None:
    if not ray.is_initialized():
        ray.init()

    global step_handler
    if not step_handler:
        view_queue = ray.util.queue.Queue()
        cmd_queue = ray.util.queue.Queue()
        step_handler = RayStepHandler.remote(cmd_queue, view_queue)
        graphbook.web.async_start(
            isolate_users=False,
            no_sample=False,
            host="0.0.0.0",
            port=8005,
            proc_queue=cmd_queue,
            view_queue=view_queue,
        )


def is_graphbook_ray_initialized() -> bool:
    return ray.is_initialized() and step_handler is not None


def run_async(
    dag: DAGNode,
    name: Optional[str] = None,
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

    if name is None:
        name = str(uuid.uuid4())

    logger.info(f'Graphbook job created. [id="{name}"].')
    context = GraphbookTaskContext(name=name)
    with graphbook_task_context(context):
        # BFS
        curr_node = None
        curr_id = None
        actor_id_to_idx = {}
        context_setup_refs = []
        nodes = []
        G = {}

        def fn(node: ClassMethodNode):
            handle: ActorHandle = node._parent_class_node
            node_context = getattr(handle, "_graphbook_context", None)
            if node_context is not None:
                nonlocal curr_node, curr_id
                curr_id = str(handle._actor_id)
                curr_node = node
                if curr_id in G:
                    return

                assert node_context is not None
                node_id = node_context["node_id"]

                node_class = node_context["class"]
                node_name = node_class.__name__[len("ActorClass(") : -1]
                if issubclass(node_class, Step):
                    G[curr_id] = {
                        "type": "step",
                        "name": node_name,
                        "parameters": deepcopy(node_class.Parameters or {}),
                        "inputs": [],
                        "outputs": node_class.Outputs or ["out"],
                        "category": node_class.Category or "",
                    }
                else:  # Resource
                    G[curr_id] = {
                        "type": "resource",
                        "name": node_name,
                        "parameters": deepcopy(node_class.Parameters or {}),
                        "category": node_class.Category or "",
                    }

                resource_deps = node_context["resource_deps"]
                parameters = G[curr_id]["parameters"]
                for k, actor_id in resource_deps.items():
                    parameters[k]["value"] = actor_id

                actor_id_to_idx[curr_id] = node_id
                context_setup = handle.set_context.remote(
                    node_id=node_id,
                    node_name=node_name,
                )
                context_setup_refs.append(context_setup)
                nodes.append((node_id, handle))
            else:  # StepHandler
                # dummy_input, step_id, *bind_args: List[Tuple[str, dict]]
                for i in range(2, len(node._bound_args), 2):
                    G[curr_id]["inputs"].append(
                        {
                            "node": str(
                                node._bound_args[i + 1]._parent_class_node._actor_id
                            ),
                            "pin": node._bound_args[i],
                        }
                    )

        dag.traverse_and_apply(fn)
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

        # Prompts for user input
        params = ray.get(step_handler.handle_new_execution.remote(name, G))

        # Set the param values to each node and other context variables
        for node_id, handle in nodes:
            node_params = params.get(node_id)
            ref = handle._set_init_params.remote(**node_params)
            context_setup_refs.append(ref)
        ray.wait(context_setup_refs)

        return execute(dag, context)


def run(
    dag: DAGNode,
    name: Optional[str] = None,
    **kwargs,
) -> Any:
    return ray.get(run_async(dag, name=name, **kwargs))


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


def make_input_grapbook_class(cls):
    assert issubclass(cls, Step) or issubclass(
        cls, Resource
    ), "Invalid Graphbook Node class."

    class DerivedGraphbookRayClass(cls):
        def __init__(self, *args, **kwargs):
            pass

        def _original_init(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _set_init_params(self, **kwargs):
            init_params = getattr(self, "_init_params", None)
            if init_params is None:
                init_params = {**kwargs}
            else:
                init_params.update(kwargs)
            setattr(self, "_init_params", init_params)

        def _patched_init_method(self, dummy_input):
            init_params = getattr(self, "_init_params", {})
            original_init_method = getattr(self, "_original_init")
            original_init_method(**init_params)

        def _call_with_dummy(self, dummy_input, *args):
            if issubclass(cls, Resource):
                return self.value()
            return self.__call__(*args)

    DerivedGraphbookRayClass.__name__ = cls.__name__
    DerivedGraphbookRayClass.__module__ = cls.__module__
    DerivedGraphbookRayClass.__qualname__ = cls.__qualname__
    DerivedGraphbookRayClass.__doc__ = cls.__doc__
    return DerivedGraphbookRayClass


class GraphbookActorWrapper:
    def __init__(self, actor, *args, **kwargs):
        self._actor = actor
        return self._actor.__init__(self, *args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self._actor.__call__(self, *args, **kwargs)

    def options(self, **kwargs):
        self._actor = GraphbookActorWrapper(self._actor.options(self, **kwargs))
        return self

    def bind():
        raise ValueError("Cannot bind right away, please call .remote() first.")

    def remote(self, *args, **kwargs):
        assert (
            len(args) == 0
        ), "To specify resources, use kwargs. (e.g. my_resource=MyResource.remote())"
        is_step = isinstance(self._actor, Step)
        init_fn = step_handler.init_step if is_step else step_handler.init_resource
        node_id = ray.get(init_fn.remote())

        actor_handle: ray.actor.ActorHandle = self._actor._remote(
            **self._actor._default_options
        )
        gb_context = {}
        gb_context["class"] = self._actor.__class__
        gb_context["node_id"] = node_id
        gb_context["resource_deps"] = {
            k: str(v._parent_class_node._actor_id) for k, v in kwargs.items()
        }
        setattr(actor_handle, "_graphbook_context", gb_context)

        requires_input = is_step and not isinstance(self._actor, SourceStep)
        if requires_input:

            def bind(self, *bind_args):
                assert (
                    len(bind_args) % 2 == 0
                ), "Bind arguments must be pairs of bind_key and bind_obj"

                dummy_input = self._set_init_params.bind(**kwargs)
                dummy_input = self._patched_init_method.bind(dummy_input)
                input_notes = step_handler.handle.bind(dummy_input, node_id, *bind_args)
                class_method_node = self.all.bind(input_notes)

                return class_method_node

            actor_handle.bind = bind.__get__(actor_handle)
            return actor_handle

        def bind(self, *args):
            raise ValueError(
                "Cannot bind a non-step node. SourceSteps and Resources should not have any inputs. To supply it with parameters, use kwargs in the .remote() call."
            )

        dummy_input = actor_handle._set_init_params.bind(**kwargs)
        dummy_input = actor_handle._patched_init_method.bind(dummy_input)
        class_method_node = actor_handle._call_with_dummy.bind(dummy_input)

        class_method_node.bind = bind.__get__(class_method_node)
        return class_method_node


def remote(*args, **kwargs) -> GraphbookActorWrapper:
    cls = args[0]
    cls = make_input_grapbook_class(cls)

    actor_class = ray.remote(cls, **kwargs)  # do something with *args[1:] ?
    gb_actor_class = GraphbookActorWrapper(actor_class)

    return gb_actor_class

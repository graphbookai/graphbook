try:
    import ray
except ImportError:
    raise ImportError(
        "ray is required for graphbook.ray. You can install all required dependencies with `pip install graphbook[ray]`"
    )


import ray.actor
import ray.util.queue
from ray.dag import DAGNode

from typing import (
    Optional,
    TypeVar,
)
from .ray_processor import (
    RayStepHandler,
    execute,
    GraphbookTaskContext,
    graphbook_task_context,
    create_graph_execution,
)
from .ray_img import RayMemoryManager
from .ray_client import RayClientPool
from graphbook.core.steps import Step, SourceStep, PromptStep, GeneratorSourceStep, BatchStep
from graphbook.core.resources import Resource
import graphbook.core.web
import multiprocessing as mp
import logging
import uuid

logger = logging.getLogger(__name__)
T = TypeVar("T")
step_handler: RayStepHandler = None


def _ensure_graphbook_initialized() -> None:
    if not is_graphbook_ray_initialized():
        init()


def init(*, host="0.0.0.0", port=8005) -> None:
    """
    Initializes Ray and Graphbook web server if not already initialized.

    Args:
        host: The host address to bind the web server to. Default is 0.0.0.0.
        port: The port to bind the web server to. Default is 8005.
    """
    if not ray.is_initialized():
        ray.init()

    global step_handler
    if not step_handler:
        view_queue = ray.util.queue.Queue()
        cmd_queue = ray.util.queue.Queue()
        step_handler = RayStepHandler.remote(cmd_queue, view_queue)
        close_event = mp.Event()
        graphbook.core.web.async_start(
            host=host,
            port=port,
            close_event=close_event,
            img_storage=RayMemoryManager,
            client_pool=RayClientPool(close_event=close_event, proc_queue=cmd_queue, view_queue=view_queue),
        )


def is_graphbook_ray_initialized() -> bool:
    """
    Returns whether the Graphbook Ray API is initialized.
    """
    return ray.is_initialized() and step_handler is not None


def run_async(
    dag: DAGNode,
    name: Optional[str] = None,
) -> ray.ObjectRef:
    """Run a workflow asynchronously.

    If the workflow with the given id already exists, it will be resumed.

    Args:
        dag: The leaf node of the DAG. Will recursively run its dependencies.
        name: A unique identifier that can be used to identify the graphbook execution
            in the web UI. If not specified, a random id will be generated.

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
        G, nodes = create_graph_execution(dag)

        # Prompts for user input
        print(f"Starting execution {name}")
        print(
            "Found parameters that need to be set. Please navigate to the Graphbook UI to set them."
        )
        params = ray.get(step_handler.handle_new_execution.remote(name, G))

        # Set the param values to each node and other context variables
        context_setup_refs = []
        for node_id, node_name, handle in nodes:
            node_params = params.get(node_id)
            ref = handle._set_init_params.remote(**node_params)
            context_setup_refs.append(ref)
            context_setup = handle.set_context.remote(
                node_id=node_id,
                node_name=node_name,
            )
            context_setup_refs.append(context_setup)

        context_setup_refs.append(step_handler.handle_start_execution.remote())
        ray.wait(context_setup_refs)
        final = step_handler.handle_end_execution.bind(dag)

        return execute(final, context)


def run(
    dag: DAGNode,
    name: Optional[str] = None,
) -> dict:
    """
    Runs a workflow synchronously. See :func:`run_async` for more details.

    Returns:
        The multi-output value of the argument leaf node.
    """
    return ray.get(run_async(dag, name=name))


def _make_input_grapbook_class(cls):
    assert issubclass(cls, Step) or issubclass(
        cls, Resource
    ), "Invalid Graphbook Node class."

    if issubclass(cls, PromptStep):
        raise ValueError("Prompting is not yet supported in Graphbook Ray API.")

    if issubclass(cls, GeneratorSourceStep):
        raise ValueError(
            "Sources with generators is not yet supported in Graphbook Ray API."
        )

    if issubclass(cls, BatchStep):
        raise ValueError(
            "Automatic batching is not yet supported in Graphbook Ray API."
        )

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
    def __init__(self, actor, doc, *args, **kwargs):
        self._actor = actor
        self._doc = doc
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
        gb_context["doc"] = self._doc
        gb_context["node_id"] = node_id
        gb_context["resource_deps"] = {
            k: str(v._parent_class_node._actor_id) for k, v in kwargs.items()
        }
        gb_context["step_deps"] = []
        setattr(actor_handle, "_graphbook_context", gb_context)

        requires_input = is_step and not isinstance(self._actor, SourceStep)
        if requires_input:

            def bind(self, *bind_args):
                assert (
                    len(bind_args) % 2 == 0
                ), "Bind arguments must be pairs of bind_key and bind_obj"

                gb_context["step_deps"] = [
                    {
                        "node": str(
                            getattr(
                                bind_args[i + 1], "_graphbook_bound_actor"
                            )._ray_actor_id
                        ),
                        "pin": bind_args[i],
                    }
                    for i in range(0, len(bind_args), 2)
                ]
                setattr(actor_handle, "_graphbook_context", gb_context)

                dummy_input = self._set_init_params.bind(**kwargs)
                dummy_input = self._patched_init_method.bind(dummy_input)
                input = step_handler.prepare_inputs.bind(
                    dummy_input, node_id, *bind_args
                )
                outputs = self.all.bind(input)
                outputs = step_handler.handle_outputs.bind(node_id, outputs)
                setattr(outputs, "_graphbook_bound_actor", actor_handle)

                return outputs

            actor_handle.bind = bind.__get__(actor_handle)
            return actor_handle

        dummy_input = actor_handle._set_init_params.bind(**kwargs)
        dummy_input = actor_handle._patched_init_method.bind(dummy_input)
        outputs = actor_handle._call_with_dummy.bind(dummy_input)

        if is_step:
            outputs = step_handler.handle_outputs.bind(node_id, outputs)
            setattr(outputs, "_graphbook_bound_actor", actor_handle)

        return outputs


def remote(*args, **kwargs) -> GraphbookActorWrapper:
    """
    Decorates the following class to be a remote actor in Ray that is also compatible with Graphbook.
    """
    cls = args[0]
    cls = _make_input_grapbook_class(cls)

    actor_class = ray.remote(cls, **kwargs)  # do something with *args[1:] ?
    gb_actor_class = GraphbookActorWrapper(actor_class, cls.__doc__)

    return gb_actor_class

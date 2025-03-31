try:
    import ray
except ImportError:
    raise ImportError(
        "ray is required for graphbook.ray. You can install all required dependencies with `pip install graphbook[ray]`"
    )


import ray.actor
import ray.util.queue
from ray.dag import DAGNode
from ray.dag import ClassMethodNode

from typing import (
    Optional,
    TypeVar,
)
from .ray_processor import (
    RayStepHandler,
    GraphbookTaskContext,
    graphbook_task_context,
)
from .ray_img import RayMemoryManager
from .ray_client import RayClientPool
from graphbook.core.steps import (
    Step,
    SourceStep,
    PromptStep,
    GeneratorSourceStep,
    BatchStep,
)
from graphbook.core.resources import Resource
import graphbook.core.web
import multiprocessing as mp
import logging

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
        # Use a single close_event for the whole system
        close_event = mp.Event()
        # Set up a cleanup handler for system exit
        import atexit

        atexit.register(lambda: close_event.set())

        # Create client pool with the same close event
        client_pool = RayClientPool(
            close_event=close_event, proc_queue=cmd_queue, view_queue=view_queue
        )

        graphbook.core.web.async_start(
            host=host,
            port=port,
            close_event=close_event,
            img_storage=RayMemoryManager,
            client_pool=client_pool,
        )


def init_handler(cmd_queue, view_queue):
    if not ray.is_initialized():
        ray.init()

    global step_handler
    if not step_handler:
        step_handler = RayStepHandler.remote(cmd_queue, view_queue)
    return step_handler


def is_graphbook_ray_initialized() -> bool:
    """
    Returns whether the Graphbook Ray API is initialized.
    """
    return ray.is_initialized() and step_handler is not None


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

        def _set_context(self, dummy_input, node_id, node_name):
            self.set_context(node_id=node_id, node_name=node_name)

    DerivedGraphbookRayClass.__name__ = cls.__name__
    DerivedGraphbookRayClass.__module__ = cls.__module__
    DerivedGraphbookRayClass.__qualname__ = cls.__qualname__
    DerivedGraphbookRayClass.__doc__ = cls.__doc__
    return DerivedGraphbookRayClass


class GraphbookActorWrapper:
    _id: int = 0

    def __init__(self, actor, doc, *args, **kwargs):
        self._actor = actor
        self._doc = doc
        self._options = {}
        self._node_id = None
        self._id = GraphbookActorWrapper._id
        GraphbookActorWrapper._id += 1
        return self._actor.__init__(self, *args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self._actor.__call__(self, *args, **kwargs)

    def set_ray_options(self, **kwargs):
        self._options = kwargs

    def set_node_id(self, node_id):
        self._node_id = node_id

    def bind():
        raise ValueError("Cannot bind right away, please call .remote() first.")

    def remote(self, **kwargs):
        is_step = isinstance(self._actor, Step)
        if self._node_id is None:
            self._node_id = str(self._id)

        node_name = self._actor.__class__.__name__[len("ActorClass(") : -1]
        actor_handle: ray.actor.ActorHandle = self._actor.options(
            **self._options
        ).remote()
        gb_context = {}
        gb_context["class"] = self._actor.__class__
        gb_context["doc"] = self._doc
        gb_context["node_id"] = self._node_id
        gb_context["resource_deps"] = {
            k: str(v._parent_class_node._actor_id)
            for k, v in kwargs.items()
            if isinstance(v, ClassMethodNode)
        }
        gb_context["step_deps"] = []
        setattr(actor_handle, "_graphbook_context", gb_context)

        requires_input = is_step and not isinstance(self._actor, SourceStep)
        if requires_input:

            node_id = self._node_id

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
                dummy_input = self._set_context.bind(dummy_input, node_id, node_name)
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
        dummy_input = actor_handle._set_context.bind(
            dummy_input, self._node_id, node_name
        )
        outputs = actor_handle._call_with_dummy.bind(dummy_input)

        if is_step:
            outputs = step_handler.handle_outputs.bind(self._node_id, outputs)
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


from graphbook.core.decorators import DecoratorFunction


def options(**kwargs):
    """
    You may specify Ray options for the remote actor.
    Ray allows you to seamlessly scale your applications from a laptop to a cluster, and this decorator will forward the given arguments to the Ray options for the remote actor.
    See `Ray Resources <https://docs.ray.io/en/latest/ray-core/scheduling/resources.html>`_ and
    `options <https://docs.ray.io/en/latest/ray-core/api/doc/ray.actor.ActorClass.options.html#ray.actor.ActorClass.options>`_ for more information.


    Examples:
        .. highlight:: python
        .. code-block:: python

            from graphbook import step
            from graphbook.ray import options

            @step("RayStep")
            @options(num_cpus=2, num_gpus=1)
            def my_ray_step(ctx, data):
                # Process some data
                data["value"] = predict(...)
    """

    def decorator(func):
        def set_options(node_class):
            node_class.Ray_Options = kwargs
            return node_class

        return DecoratorFunction(func, set_options)

    return decorator

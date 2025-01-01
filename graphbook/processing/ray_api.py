import ray
import time, uuid
from ray.dag import DAGNode, DAGInputData
from typing import Any, Dict, Optional, Generator, Union, Callable, TypeVar, List
from contextlib import contextmanager
from dataclasses import dataclass
from graphbook.processing.ray_processor import GraphbookExecutor
import graphbook.web
from graphbook.processing.ray_processor import RayProcessor
import multiprocessing as mp
import ray.dag.class_node as class_node
import os

import inspect
import ray.actor

from ray.workflow.common import (
    validate_user_metadata,
)

import logging

logger = logging.getLogger(__name__)
global graphbook_context
T = TypeVar("T")


def _ensure_graphbook_initialized() -> None:
    # NOTE: Trying to get the actor has a side effect: it initializes Ray with
    # default arguments. This is different in "init()": it assigns a temporary
    # storage. This is why we need to check "ray.is_initialized()" first.
    if not ray.is_initialized():
        init()
    # else:
    #     try:
    #         workflow_access.get_management_actor()
    #     except ValueError:
    #         init()


def init(
    *,
    max_running_workflows: Optional[int] = None,
    max_pending_workflows: Optional[int] = None,
) -> None:
    """Initialize workflow.

    If Ray is not initialized, we will initialize Ray and
    use ``/tmp/ray/workflow_data`` as the default storage.

    Args:
        max_running_workflows: The maximum number of concurrently running workflows.
            Use -1 as infinity. 'None' means preserving previous setting or initialize
            the setting with infinity.
        max_pending_workflows: The maximum number of queued workflows.
            Use -1 as infinity. 'None' means preserving previous setting or initialize
            the setting with infinity.
    """
    # usage_lib.record_library_usage("graphbook")

    if max_running_workflows is not None:
        if not isinstance(max_running_workflows, int):
            raise TypeError("'max_running_workflows' must be None or an integer.")
        if max_running_workflows < -1 or max_running_workflows == 0:
            raise ValueError(
                "'max_running_workflows' must be a positive integer "
                "or use -1 as infinity."
            )
    if max_pending_workflows is not None:
        if not isinstance(max_pending_workflows, int):
            raise TypeError("'max_pending_workflows' must be None or an integer.")
        if max_pending_workflows < -1:
            raise ValueError(
                "'max_pending_workflows' must be a non-negative integer "
                "or use -1 as infinity."
            )

    if not ray.is_initialized():
        # We should use get_temp_dir_path, but for ray client, we don't
        # have this one. We need a flag to tell whether it's a client
        # or a driver to use the right dir.
        # For now, just use $TMP/ray/workflow_data
        # workflow_dir = Path(tempfile.gettempdir()) / "ray" / "graphbook_data"
        # ray.init(storage=workflow_dir.as_uri())
        ray.init()
        graphbook.web.async_start(False, False, "0.0.0.0", 8005)


def run_async(
    dag: DAGNode,
    *args,
    workflow_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ray.ObjectRef:
    """Run a workflow asynchronously.

    If the workflow with the given id already exists, it will be resumed.

    Args:
        workflow_id: A unique identifier that can be used to resume the
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

    if workflow_id is None:
        # Workflow ID format: {Entry workflow UUID}.{Unix time to nanoseconds}
        workflow_id = f"{str(uuid.uuid4())}.{time.time():.9f}"

    # workflow_manager = workflow_access.get_management_actor()
    # if ray.get(workflow_manager.is_workflow_non_terminating.remote(workflow_id)):
    #     raise RuntimeError(f"Workflow '{workflow_id}' is already running or pending.")

    # state = workflow_state_from_dag(dag, input_data, workflow_id)
    logger.info(f'Graphbook job created. [id="{workflow_id}"].')
    context = GraphbookTaskContext(workflow_id=workflow_id)
    with graphbook_task_context(context):
        # job_id = ray.get_runtime_context().get_job_id()
        return execute(dag, input_data, context)


def run(
    dag: DAGNode,
    *args,
    workflow_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Any:
    """Run a workflow.

    If the workflow with the given id already exists, it will be resumed.

    Examples:
        .. testcode::

            import ray
            from ray import workflow

            @ray.remote
            def book_flight(origin: str, dest: str):
               return f"Flight: {origin}->{dest}"

            @ray.remote
            def book_hotel(location: str):
               return f"Hotel: {location}"

            @ray.remote
            def finalize_trip(bookings: List[Any]):
               return ' | '.join(ray.get(bookings))

            flight1 = book_flight.bind("OAK", "SAN")
            flight2 = book_flight.bind("SAN", "OAK")
            hotel = book_hotel.bind("SAN")
            trip = finalize_trip.bind([flight1, flight2, hotel])
            print(workflow.run(trip))

        .. testoutput::

            Flight: OAK->SAN | Flight: SAN->OAK | Hotel: SAN

    Args:
        workflow_id: A unique identifier that can be used to resume the
            workflow. If not specified, a random id will be generated.
        metadata: The metadata to add to the workflow. It has to be able
            to serialize to json.

    Returns:
        The running result.
    """
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
    view_manger_queue = mp.Queue()
    processor: RayProcessor = RayProcessor(view_manger_queue, False, False, None)


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


# @ray.remote(num_cpus=0)
def execute(
    dag: DAGNode, dag_input: DAGInputData, context: GraphbookTaskContext
) -> None:
    # executor = WorkflowExecutor(state)
    # try:
    #     await executor.run_until_complete(job_id, context, wf_store)
    #     return await self.get_output(workflow_id, executor.output_task_id)
    # finally:
    #     pass
    """Execute a submitted workflow.

    Args:
        job_id: The ID of the job for logging.
        context: The execution context.
    Returns:
        An object ref that represent the result.
    """
    executor = GraphbookExecutor()
    try:
        return executor.run_until_complete(dag, dag_input, context)
    finally:
        pass
        # self._workflow_executors.pop(workflow_id)
        # self._running_workflows.remove(workflow_id)
        # self._executed_workflows.add(workflow_id)
        # if not self._workflow_queue.empty():
        #     # schedule another workflow from the pending queue
        #     next_workflow_id = self._workflow_queue.get_nowait()
        #     self._running_workflows.add(next_workflow_id)
        #     fut = self._queued_workflows.pop(next_workflow_id)
        #     fut.set_result(None)


class GraphbookClassMethodNode(class_node.ClassMethodNode):
    def __init__(self, bind_key):
        self.bind_key = bind_key
        self.outputs = {}

    def _execute_impl(self, *args, **kwargs):
        print("Executing...")

        if self.is_class_method_call:
            method_body = getattr(self._parent_class_node, self._method_name)

            # @ray.remote # Cannot wrap this remote function with another remote function
            # So, this unwrapping needs to happen in the remote function
            # However, doing it in the remote function can cause it to be called multiple times.
            # So, we need to cache the result of the unwrapping.

            # def local_impl(*args, **kwargs):
            #     output = method_body(*args, **kwargs)
            #     for key, value in output.items():
            #         self.outputs[key] = value

            # Execute with bound args.
            # return local_impl.options(**self._bound_options).remote(
            #     *self._bound_args,
            #     **self._bound_kwargs,
            # )
            
            # Execute with bound args.
            return method_body.options(**self._bound_options).remote(
                *self._bound_args,
                **self._bound_kwargs,
            )
        else:
            assert self._class_method_output is not None
            return self._bound_args[0][self._class_method_output.output_idx]

    def _copy_impl(
        self,
        new_args: List[Any],
        new_kwargs: Dict[str, Any],
        new_options: Dict[str, Any],
        new_other_args_to_resolve: Dict[str, Any],
    ):
        class_method_node = super()._copy_impl(
            new_args, new_kwargs, new_options, new_other_args_to_resolve
        )
        gb_class_method_node = GraphbookClassMethodNode(self.bind_key)
        gb_class_method_node.__dict__.update(class_method_node.__dict__)
        return gb_class_method_node

    def apply_recursive(self, fn: "Callable[[DAGNode], T]") -> T:
        """Apply callable on each node in this DAG in a bottom-up tree walk.

        Args:
            fn: Callable that will be applied once to each node in the
                DAG. It will be applied recursively bottom-up, so nodes can
                assume the fn has been applied to their args already.

        Returns:
            Return type of the fn after application to the tree.
        """

        if not type(fn).__name__ == "_CachingFn":

            class _CachingFn:
                def __init__(self, fn):
                    self.cache = {}
                    self.fn = fn
                    self.fn.cache = self.cache
                    self.input_node_uuid = None

                def __call__(self, node: "GraphbookClassMethodNode"):
                    from ray.dag.input_node import InputNode

                    if node._stable_uuid not in self.cache:
                        fn_out = self.fn(node)
                        print("fn_out", fn_out)
                        self.cache[node._stable_uuid] = fn_out
                    if isinstance(node, InputNode):
                        if not self.input_node_uuid:
                            self.input_node_uuid = node._stable_uuid
                        elif self.input_node_uuid != node._stable_uuid:
                            raise AssertionError(
                                "Each DAG should only have one unique InputNode."
                            )
                    return self.cache[node._stable_uuid]

            fn = _CachingFn(fn)
        else:
            if self._stable_uuid in fn.cache:
                # self.outputs[]
                return fn.cache[self._stable_uuid]

        return fn(
            self._apply_and_replace_all_child_nodes(
                lambda node: node.apply_recursive(fn)
            )
        )

    def execute(self, *args, **kwargs):
        def executor(node):
            return node._execute_impl(*args, **kwargs)

        result = self.apply_recursive(executor)
        print("result", result)
        self.cache_from_last_execute = executor.cache
        print("cache", self.cache_from_last_execute)
        return result


class GraphbookActorClass:
    def __init__(self, actor: ray.actor.ActorClass):
        self._actor = actor

    def remote(self, *args, **kwargs):
        """Create an actor.

        Args:
            args: These arguments are forwarded directly to the actor
                constructor.
            kwargs: These arguments are forwarded directly to the actor
                constructor.

        Returns:
            A handle to the newly created actor.
        """

        actor_handle: ray.actor.ActorHandle = self._actor._remote(
            args=args, kwargs=kwargs, **self._actor._default_options
        )

        def bind(self, bind_key: str, *args, **kwargs):
            class_method_node = self.__call__.bind(*args, **kwargs)
            gb_class_method_node = GraphbookClassMethodNode(bind_key)
            gb_class_method_node.__dict__.update(class_method_node.__dict__)
            return gb_class_method_node

        actor_handle.bind = bind.__get__(actor_handle)
        return actor_handle


def remote(
    *args, **kwargs
) -> Union[
    ray.remote_function.RemoteFunction, ray.actor.ActorClass, GraphbookActorClass
]:
    actor_class = ray.remote(*args, **kwargs)
    gb_actor_class = GraphbookActorClass(actor_class)
    return gb_actor_class

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import multiprocessing as mp
import traceback
import time
import copy
from PIL import Image

from ..steps import (
    Step,
    SourceStep,
    GeneratorSourceStep,
    AsyncStep,
    BatchStep,
    log,
)
from ..dataloading import Dataloader
from ..utils import transform_json_log, ExecutionContext
from .state import GraphState, StepState
from ..viewer import MultiGraphViewManagerInterface
from ..shm import MultiThreadedMemoryManager, ImageStorageInterface
import abc
from graphbook.core.clients import SimpleClientPool, ClientPool
from graphbook.core.shm import MultiThreadedMemoryManager

if TYPE_CHECKING:
    from ..serialization import Graph

step_output_err_res = "Step output must be a dictionary, and dict values must be lists."


class Executor(abc.ABC):
    """
    Base class for execution engines that can run Graphbook workflows.
    """

    @abc.abstractmethod
    def run(self, graph: "Graph", step_id: Optional[str] = None):
        """
        Execute the provided graph.

        Args:
            graph (Dict[str, Any]): The serialized graph to execute
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
        """
        pass

    @abc.abstractmethod
    def get_client_pool(self) -> ClientPool:
        pass

    @abc.abstractmethod
    def get_img_storage(self) -> ImageStorageInterface:
        pass


class DefaultExecutor(Executor):
    """
    Default execution engine that runs Graphbook workflows using the GraphProcessor.
    """

    def __init__(
        self,
        continue_on_failure: bool = False,
        copy_outputs: bool = True,
        num_workers: int = 1,
    ):
        """
        Initialize the DefaultExecutor.

        Args:
            continue_on_failure (bool): Whether to continue execution after a step fails
            copy_outputs (bool): Whether to make deep copies of step outputs
            num_workers (int): Number of workers for batch processing
        """
        # Import here to avoid circular imports
        from graphbook.core.processing.graph_processor import GraphProcessor

        self.view_manager_queue = mp.Queue()

        self.processor = GraphProcessor(
            self.view_manager_queue,
            continue_on_failure,
            copy_outputs,
            num_workers,
        )
        self.client_pool = SimpleClientPool(
            self.processor.close_event, self.view_manager_queue, self.processor
        )

    def get_client_pool(self):
        return self.client_pool

    def get_img_storage(self):
        return MultiThreadedMemoryManager

    def run(self, graph: "Graph", step_id: Optional[str] = None):
        """
        Execute the provided graph.

        Args:
            graph (Dict[str, Any]): The serialized graph to execute
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
        """

        try:
            # Execute the workflow directly
            self.processor.run(graph, step_id)

        except Exception as e:
            log(f"Execution error: {type(e).__name__}: {str(e)}", "error")
            traceback.print_exc()
            return None, None

    def __del__(self):
        """Clean up resources when the executor is garbage collected."""
        if hasattr(self, "processor"):
            self.processor.stop()


class GraphProcessor:
    """
    Lightweight processor for running Graph objects directly without requiring file system setup.
    """

    def __init__(
        self,
        view_manager_queue: mp.Queue,
        continue_on_failure: bool = False,
        copy_outputs: bool = True,
        num_workers: int = 1,
    ):
        """
        Initialize the GraphProcessor.

        Args:
            continue_on_failure (bool): Whether to continue execution after a step fails
            copy_outputs (bool): Whether to make deep copies of step outputs
            num_workers (int): Number of workers for batch processing
        """
        self.close_event = mp.Event()
        self.view_manager_queue = view_manager_queue
        self.continue_on_failure = continue_on_failure
        self.copy_outputs = copy_outputs
        self.num_workers = num_workers
        self.view_manager = MultiGraphViewManagerInterface(self.view_manager_queue)
        self.viewer = self.view_manager.new("memory_workflow")

        # Initialize state
        self.graph_state = GraphState(None)  # No custom nodes path needed

        # Initialize dataloader
        self.dataloader = Dataloader(self.num_workers, False)

    def handle_images(self, outputs: Dict[str, List[Any]]):
        """Handle images in step outputs by storing them in shared memory."""

        def try_add_image(item):
            if isinstance(item, dict):
                if item.get("shm_id") is not None:
                    return
                if item.get("type") == "image" and isinstance(
                    item.get("value"), Image.Image
                ):
                    shm_id = MultiThreadedMemoryManager.add_image(item["value"])
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

    def exec_step(
        self, step: Step, input: Optional[Any] = None, flush: bool = False
    ) -> Optional[Dict[str, List[Any]]]:
        """Execute a single step with optional input."""
        ExecutionContext.update(node_id=step.id)
        ExecutionContext.update(node_name=step.__class__.__name__)
        outputs = {}
        step_fn = step if not flush else step.all
        start_time = time.time()

        try:
            if input is None:
                outputs = step_fn()
            else:
                if isinstance(step, AsyncStep):
                    step.in_q(input)
                    outputs = step_fn()
                else:
                    outputs = step_fn(input)
        except Exception as e:
            log(f"{type(e).__name__}: {str(e)}", "error")
            traceback.print_exc()
            return None

        if outputs:
            if not isinstance(outputs, dict):
                if not len(step.Outputs) == 1:
                    log(
                        f"{step_output_err_res} Output was not a dict. This step has multiple outputs {step.Outputs} and cannot assume a single value.",
                        "error",
                    )
                    return None
                outputs = {step.Outputs[0]: outputs}

            for k, v in outputs.items():
                if not isinstance(v, list):
                    outputs[k] = [v]

            self.handle_images(outputs)
            self.graph_state.handle_outputs(
                step.id, outputs if not self.copy_outputs else copy.deepcopy(outputs)
            )
            self.viewer.handle_time(step.id, time.time() - start_time)
        return outputs

    def handle_steps(self, steps: List[Step]) -> bool:
        """Process a sequence of steps, handling dependencies."""
        is_active = False
        for step in steps:
            output = {}
            if isinstance(step, GeneratorSourceStep):
                output = self.exec_step(step)
            elif isinstance(step, SourceStep):
                if not self.graph_state.get_state(step, StepState.EXECUTED):
                    output = self.exec_step(step)
            else:
                try:
                    input = self.graph_state.get_input(step)
                    is_active = True
                except StopIteration:
                    input = None

                if isinstance(step, AsyncStep):
                    if is_active:  # parent is active
                        # Proceed with normal step execution
                        output = self.exec_step(step, input)
                    else:
                        # Flush queue and proceed with normal execution
                        output = self.exec_step(step, flush=True)
                    is_active = is_active or step.is_active()
                else:
                    if input:
                        output = self.exec_step(step, input)

            if output is None:
                if not self.continue_on_failure:
                    return False
                else:
                    output = {}
            else:
                if not is_active:
                    is_active = any(len(v) > 0 for v in output.values())

        return is_active

    def try_execute_step_event(self, step: Step, event: str):
        """Try to execute a lifecycle event (on_start/on_end) for a step."""
        ExecutionContext.update(node_id=step.id)
        ExecutionContext.update(node_name=step.__class__.__name__)
        try:
            if hasattr(step, event):
                getattr(step, event)()
                return True
        except Exception as e:
            log(f"{type(e).__name__}: {str(e)}", "error")
            traceback.print_exc()
        return False

    def run(self, graph: "Graph", step_id: Optional[str] = None):
        """Run the entire graph or a specific step."""
        # Initialize viewer
        ExecutionContext.update(view_manager=self.viewer, dataloader=self.dataloader)
        self.viewer.set_state("run_state", "running")
        self.viewer.set_state("graph_state", graph.serialize())
        self.graph_state.set_viewer(self.viewer)

        # Update graph state with provided graph
        self.graph_state.update_state_py(graph, {})

        # Handle resources
        resource_values = self.graph_state.get_resource_values()
        for resource_id, value in resource_values.items():
            self.viewer.handle_output(
                resource_id, "resource", transform_json_log(value)
            )

        # Get processing steps
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)

        # Execute start events
        for step in steps:
            self.viewer.handle_start(step.id)
            succeeded = self.try_execute_step_event(step, "on_start")
            if not succeeded:
                self.viewer.set_state("run_state", "finished")
                return

        # Set up dataloader
        self.setup_dataloader(steps)

        # Execute steps
        dag_is_active = True
        try:
            while (
                dag_is_active
                and not self.close_event.is_set()
                and not self.dataloader.is_failed()
            ):
                dag_is_active = self.handle_steps(steps)
        finally:
            self.viewer.handle_end()
            self.viewer.set_state("run_state", "finished")
            self.dataloader.stop()
            for step in steps:
                self.try_execute_step_event(step, "on_end")

    def setup_dataloader(self, steps: List[Step]):
        """Set up the dataloader for batch steps."""
        dataloader_consumers = [step for step in steps if isinstance(step, BatchStep)]
        consumer_ids = [id(c) for c in dataloader_consumers]
        consumer_load_fn = [
            c.load_fn if hasattr(c, "load_fn") else None for c in dataloader_consumers
        ]
        consumer_dump_fn = [
            c.dump_fn if hasattr(c, "dump_fn") else None for c in dataloader_consumers
        ]
        self.dataloader.start(consumer_ids, consumer_load_fn, consumer_dump_fn)

    def get_output(self, step_id: str, pin_id: str, index: int) -> Optional[Any]:
        """Get a specific output from a step."""
        output = self.graph_state.get_output(step_id, pin_id, index)
        return transform_json_log(output)

    def stop(self):
        """Stop the processor and clean up resources."""
        self.close_event.set()
        self.dataloader.shutdown()

    def handle_prompt_response(self, step_id: str, response: str) -> bool:
        """Handle a prompt response for a step."""
        return self.graph_state.handle_prompt_response(step_id, response)

    def get_worker_queue_sizes(self):
        return self.dataloader.get_all_sizes()

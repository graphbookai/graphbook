from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING, Set
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
    StepOutput,
)
from ..dataloading import Dataloader
from ..utils import transform_json_log, ExecutionContext
from .graph_state import GraphState, StepState
from ..viewer import MultiGraphViewManagerInterface
from ..shm import MultiThreadedMemoryManager, ImageStorageInterface
from ..output_log import OutputLogManager
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
    def run(self, graph: "Graph", name: str, step_id: Optional[str] = None) -> None:
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
        copy_outputs: bool = True,
        num_workers: int = 1,
        output_log_dir: Optional[str] = None,
    ):
        """
        Initialize the DefaultExecutor.

        Args:
            copy_outputs (bool): Whether to make deep copies of step outputs
            num_workers (int): Number of workers for batch processing
            output_log_dir (Optional[str]): Directory to store output logs
        """

        self.copy_outputs = copy_outputs
        self.num_workers = num_workers
        self.output_log_dir = output_log_dir
        self.view_manager_queue = mp.Queue()

        self.processor = GraphProcessor(
            self.view_manager_queue,
            self.copy_outputs,
            self.num_workers,
            self.output_log_dir,
        )

        self.client_pool = SimpleClientPool(
            mp.Event(), self.view_manager_queue, self.processor
        )

    def get_client_pool(self):
        return self.client_pool

    def get_img_storage(self):
        return MultiThreadedMemoryManager

    def run(self, graph: "Graph", name: str, step_id: Optional[str] = None):
        """
        Execute the provided graph.

        Args:
            graph (Dict[str, Any]): The serialized graph to execute
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
        """

        try:
            # Execute the workflow directly
            self.processor.run(graph, name, step_id)

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
        copy_outputs: bool = True,
        num_workers: int = 1,
        output_log_dir: Optional[str] = None,
    ):
        """
        Initialize the GraphProcessor.

        Args:
            view_manager_queue (mp.Queue): Queue for communicating with the view manager
            copy_outputs (bool): Whether to make deep copies of step outputs
            num_workers (int): Number of workers for batch processing
            output_log_dir (Optional[str]): Directory to store output logs
        """
        self.close_event = mp.Event()
        self.view_manager_queue = view_manager_queue
        self.copy_outputs = copy_outputs
        self.num_workers = num_workers

        # Initialize output log manager
        self.output_log_manager = (
            OutputLogManager(output_log_dir) if output_log_dir else None
        )
        self.output_log_writer = None

        # Initialize state
        self.graph_state = GraphState(None)  # No custom nodes path needed
        self.curr_outputs: Dict[str, StepOutput] = {}

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
        self,
        step: Step,
        input: Optional[Any] = None,
        flush: bool = False,
    ) -> Optional[Dict[str, List[Any]]]:
        """
        Execute a single step with optional input.

        Args:
            step: The step to execute
            input: Input data for the step
            flush: Whether to flush the step (for AsyncStep)
            for_viewers: Whether to handle outputs for viewers (set to False in recursive processing)
        """
        ExecutionContext.update(node_id=step.id)
        ExecutionContext.update(node_name=step.__class__.__name__)
        outputs = {}
        step_fn = step if not flush else step.all

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
            error_msg = f"{type(e).__name__}: {str(e)}"
            log(error_msg, "error")
            # Log the error to the output log file if available
            if self.output_log_writer:
                self.output_log_writer.write_log(step.id, error_msg, "error")
            traceback.print_exc()
            return None

        if outputs:
            if not isinstance(outputs, dict):
                if not len(step.Outputs) == 1:
                    error_msg = f"{step_output_err_res} Output was not a dict. This step has multiple outputs {step.Outputs} and cannot assume a single value."
                    log(error_msg, "error")
                    if self.output_log_writer:
                        self.output_log_writer.write_log(step.id, error_msg, "error")
                    return None
                outputs = {step.Outputs[0]: outputs}

            for k, v in outputs.items():
                if not isinstance(v, list):
                    outputs[k] = [v]

            self.handle_images(outputs)

            # Log outputs to file if output logging is enabled
            if self.output_log_writer:
                for pin_id, output_list in outputs.items():
                    for idx, output in enumerate(output_list):
                        self.output_log_writer.write_output(
                            step.id, pin_id, idx, output
                        )

        return outputs

    def process_step_recursive(self, step: Step, is_active: bool = False) -> bool:
        """
        Process a step and its child steps recursively.

        Args:
            step: The step to process
            is_active: Whether the parent is active

        Returns:
            is_active
        """
        outputs = {}

        # Process source steps
        if isinstance(step, GeneratorSourceStep):
            outputs = self.exec_step(step)
        elif isinstance(step, SourceStep):
            if not self.graph_state.get_state(step, StepState.EXECUTED):
                outputs = self.exec_step(step)
        else:
            # For non-source steps, we need to process parents first to get inputs
            # For recursive processing, we'll process the parent steps directly
            # instead of using the queue mechanism
            parents = self.graph_state.get_parents(step)
            if parents:
                parent_active = False

                # Process all parent steps
                for parent_id in parents:
                    parent_step = self.graph_state._steps[parent_id]
                    curr_parent_active = self.process_step_recursive(parent_step)
                    parent_active = parent_active or curr_parent_active

                for parent_id, parent_slots in parents.items():
                    if parent_id not in self.curr_outputs:
                        continue
                    parent_outputs = [
                        out
                        for parent_slot in parent_slots
                        for out in self.curr_outputs[parent_id].get(parent_slot, [])
                    ]  # TODO: Instead, this needs to be a dynamic queue where if all steps consume, the queue shrinks (lpop happens upon complete consumption of leftmost element)
                    for parent_output in parent_outputs:
                        outputs = self.exec_step(step, parent_output)

            # Handle AsyncStep
            if isinstance(step, AsyncStep):
                if is_active:  # parent is active
                    # Skip - already processed above
                    pass
                else:
                    # Flush queue and proceed with normal execution
                    outputs = self.exec_step(step, flush=True)
                is_active = is_active or step.is_active()

        # Check for NULL outputs
        if outputs is None:
            return False

        # Check if this step has any outputs
        if not is_active:
            is_active = any(len(v) > 0 for v in outputs.values())

        # Update output state
        if step.id not in self.curr_outputs:
            self.curr_outputs[step.id] = {}
        for output_pin, output_values in outputs.items():
            if output_pin not in self.curr_outputs[step.id]:
                self.curr_outputs[step.id][output_pin] = []
            self.curr_outputs[step.id][output_pin].extend(output_values)

        return is_active

    def handle_steps(self, steps: List[Step]) -> bool:
        """
        Process a sequence of steps, handling dependencies using recursive approach.

        This is a replacement for the original handle_steps that uses a recursive approach
        to immediately consume outputs rather than storing them in memory.
        """
        is_active = False

        # Find terminal steps (nodes with no children)
        leaf_steps = []
        for step in steps:
            if not self.graph_state._step_graph["child"].get(step.id, set()):
                leaf_steps.append(step)

        # Process terminal steps and their dependencies recursively
        for step in leaf_steps:
            step_active, _ = self.process_step_recursive(step)
            is_active = is_active or step_active

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

    def run(self, graph: "Graph", name: str, step_id: Optional[str] = None):
        """Run the entire graph or a specific step."""
        # Initialize viewer
        self.name = name
        self.view_manager = MultiGraphViewManagerInterface(self.view_manager_queue)
        self.viewer = self.view_manager.new(name)
        ExecutionContext.update(
            view_manager=self.viewer, dataloader=self.dataloader, graph_processor=self
        )
        self.viewer.set_state("run_state", "running")
        self.viewer.set_state("graph_state", graph.serialize())
        self.graph_state.set_viewer(self.viewer)

        # Initialize output log writer if output logging is enabled
        if self.output_log_manager:
            self.output_log_writer = self.output_log_manager.get_writer(self.name)

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
        """
        Get a specific output from a step.

        This method first tries to get the output from memory. If not found
        and output logging is enabled, it tries to get it from the log file.
        """
        # Try to get output from memory first
        output = None
        if self.memory_mode != "none":
            output = self.graph_state.get_output(step_id, pin_id, index)

        # If not found in memory and output logging is enabled, try to get it from the log file
        if output is None and self.output_log_manager:
            log_reader = self.output_log_manager.get_reader(self.name)
            if log_reader:
                output = log_reader.get_output(step_id, pin_id, index)

        return transform_json_log(output)

    def stop(self):
        """Stop the processor and clean up resources."""
        self.close_event.set()
        self.dataloader.shutdown()

        # Close output log files
        if self.output_log_manager:
            self.output_log_manager.close()

    def handle_prompt_response(self, step_id: str, response: str) -> bool:
        """Handle a prompt response for a step."""
        return self.graph_state.handle_prompt_response(step_id, response)

    def get_worker_queue_sizes(self):
        return self.dataloader.get_all_sizes()

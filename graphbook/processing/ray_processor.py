from typing import Dict, List, Iterator, Optional, Tuple, Any, TYPE_CHECKING

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from ray import ObjectRef
from ray.dag import DAGNode, DAGInputData

import ray
from ray.exceptions import RayTaskError, RayError

from ray.workflow.common import (
    WorkflowRef,
    WorkflowExecutionMetadata,
    WorkflowStatus,
    TaskID,
)
from ray.workflow.exceptions import WorkflowCancellationError, WorkflowExecutionError
from ray.workflow.task_executor import get_task_executor, _BakedWorkflowInputs
from ray.workflow.workflow_state import (
    WorkflowExecutionState,
    TaskExecutionMetadata,
    Task,
)
from graphbook.processing.node import GraphbookNode

if TYPE_CHECKING:
    from graphbook.processing.ray_api import GraphbookTaskContext

logger = logging.getLogger(__name__)


@dataclass
class GraphbookRef:
    """This class represents a reference of a workflow output.

    A reference means the workflow has already been executed,
    and we have both the workflow task ID and the object ref to it
    living outputs.

    This could be used when you want to return a running workflow
    from a workflow task. For example, the remaining workflows
    returned by 'workflow.wait' contains a static ref to these
    pending workflows.
    """

    # The ID of the task that produces the output of the workflow.
    task_id: TaskID
    # The ObjectRef of the output. If it is "None", then the output has been
    # saved in the storage, and we need to check the workflow management actor
    # for the object ref.
    ref: Optional[ObjectRef] = None

    @classmethod
    def from_output(cls, task_id: str, output: Any):
        """Create static ref from given output."""
        if not isinstance(output, cls):
            if not isinstance(output, ray.ObjectRef):
                output = ray.put(output)
            output = cls(task_id=task_id, ref=output)
        return output

    def __hash__(self):
        return hash(self.task_id)

class GraphbookExecutor:
    def __init__(
        self,
        taskID: TaskID = None,
    ):
        """The core logic of executing a workflow.

        This class is responsible for:

        - Dependency resolving.
        - Task scheduling.
        - Reference counting.
        - Garbage collection.
        - Continuation handling and scheduling.
        - Error handling.
        - Responding callbacks.

        It borrows some design of event loop in asyncio,
        e.g., 'run_until_complete'.

        Args:
            state: The initial state of the workflow.
        """
        self._taskID = taskID
        self._completion_queue = asyncio.Queue()
        self._task_done_callbacks: Dict[TaskID, List[asyncio.Future]] = defaultdict(
            list
        )

    def is_running(self) -> bool:
        """The state is running, if there are tasks to be run or running tasks."""
        return True


    def run_until_complete(self, dag: DAGNode, dag_input: DAGInputData, context: "GraphbookTaskContext"):
        """Drive the state util it completes.

        Args:
            job_id: The Ray JobID for logging properly.
            context: The context of workflow execution.

        # TODO(suquark): move job_id inside context
        """
        workflow_id = context.workflow_id
        logger.info(f"Workflow job [id={workflow_id}] started.")
        return ray.get(dag.execute(dag_input))
        

    def cancel(self) -> None:
        """Cancel the running workflow."""
        for fut, workflow_ref in self._state.running_frontier.items():
            fut.cancel()
            try:
                ray.cancel(workflow_ref.ref, force=True)
            except Exception:
                pass

    def _poll_queued_tasks(self) -> List[TaskID]:
        tasks = []
        while True:
            task_id = self._state.pop_frontier_to_run()
            if task_id is None:
                break
            tasks.append(task_id)
        return tasks

    def _submit_ray_task(self, task_id: TaskID, job_id: str) -> None:
        """Submit a workflow task as a Ray task."""
        baked_inputs = _BakedWorkflowInputs(
            args=state.task_input_args[task_id],
            workflow_refs=[
                state.get_input(d) for d in state.upstream_dependencies[task_id]
            ],
        )
        task = state.tasks[task_id]
        executor = get_task_executor(task.options)
        metadata_ref, output_ref = executor(
            task.func_body,
            state.task_context[task_id],
            job_id,
            task_id,
            baked_inputs,
            task.options,
        )
        # The input workflow is not a reference to an executed workflow.
        future = asyncio.wrap_future(metadata_ref.future())
        future.add_done_callback(self._completion_queue.put_nowait)

        state.insert_running_frontier(future, WorkflowRef(task_id, ref=output_ref))
        state.task_execution_metadata[task_id] = TaskExecutionMetadata(
            submit_time=time.time()
        )

    def _post_process_submit_task(
        self, task_id: TaskID
    ) -> None:
       pass

    # def _garbage_collect(self) -> None:
    #     """Garbage collect the output refs of tasks.

    #     Currently, this is done after task submission, because when a task
    #     starts, we no longer needs its inputs (i.e. outputs from other tasks).

    #     # TODO(suquark): We may need to improve garbage collection
    #     #  when taking more fault tolerant cases into consideration.
    #     """
    #     state = self._state
    #     while state.free_outputs:
    #         # garbage collect all free outputs immediately
    #         gc_task_id = state.free_outputs.pop()
    #         assert state.get_input(gc_task_id) is not None
    #         state.output_map.pop(gc_task_id, None)

    async def _poll_ready_tasks(self) -> List[asyncio.Future]:
        cq = self._completion_queue
        ready_futures = []
        rf = await cq.get()
        ready_futures.append(rf)
        # get all remaining futures in the queue
        while not cq.empty():
            ready_futures.append(cq.get_nowait())
        return ready_futures

    def get_task_output_async(self, task_id: Optional[TaskID]) -> asyncio.Future:
        """Get the output of a task asynchronously.

        Args:
            task_id: The ID of task the callback associates with.

        Returns:
            A callback in the form of a future that associates with the task.
        """
        state = self._state
        if self._task_done_callbacks[task_id]:
            return self._task_done_callbacks[task_id][0]

        fut = asyncio.Future()
        task_id = state.continuation_root.get(task_id, task_id)
        output = state.get_input(task_id)
        if output is not None:
            fut.set_result(output)
        elif task_id in state.done_tasks:
            fut.set_exception(
                ValueError(
                    f"Task '{task_id}' is done but neither in memory or in storage "
                    "could we find its output. It could because its in memory "
                    "output has been garbage collected and the task did not"
                    "checkpoint its output."
                )
            )
        else:
            self._task_done_callbacks[task_id].append(fut)
        return fut


from ..steps import (
    Step,
    SourceStep,
    GeneratorSourceStep,
    AsyncStep,
    BatchStep,
    StepOutput,
    log,
)
from ..utils import MP_WORKER_TIMEOUT, transform_json_log, ExecutionContext
from .state import GraphState, StepState, NodeInstantiationError
from ..viewer import ViewManagerInterface
from ..note import Note
from typing import List
from pathlib import Path
import queue
import multiprocessing as mp
import threading as th
import traceback
import time
import copy

step_output_err_res = (
    "Step output must be a dictionary, and dict values must be lists of notes."
)


class RayProcessor:
    def __init__(
        self,
        view_manager_queue: mp.Queue,
        continue_on_failure: bool,
        copy_outputs: bool,
        custom_nodes_path: Path,
        num_workers: int = 1,
    ):
        self.cmd_queue = mp.Queue()
        self.view_manager = ViewManagerInterface(view_manager_queue)
        self.graph_state = GraphState(custom_nodes_path, view_manager_queue)
        self.continue_on_failure = continue_on_failure
        self.copy_outputs = copy_outputs
        self.num_workers = num_workers
        self.close_event = mp.Event()
        self.pause_event = mp.Event()
        self.is_running = False
        self.filename = None
        self.thread = th.Thread(target=self.start_loop, daemon=True)

    def exec_step(
        self, step: Step, input: Note | None = None, flush: bool = False
    ) -> StepOutput | None:
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

            if not all(
                [all(isinstance(v, Note) for v in out) for out in outputs.values()]
            ):
                log(
                    f"{step_output_err_res} List values did not all contain Notes.",
                    "error",
                )
                return None
            self.graph_state.handle_outputs(
                step.id, outputs if not self.copy_outputs else copy.deepcopy(outputs)
            )
            self.view_manager.handle_time(step.id, time.time() - start_time)
        return outputs

    def handle_steps(self, steps: List[Step]) -> bool:
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

    def step_until_received_output(self, steps: List[Step], step_id: str):
        is_active = True
        step_executed = False
        while (
            is_active
            and not step_executed
            and not self.pause_event.is_set()
            and not self.close_event.is_set()
        ):
            is_active = self.handle_steps(steps)
            step_executed = self.graph_state.get_state(
                step_id, StepState.EXECUTED_THIS_RUN
            )

    def try_execute_step_event(self, step: Step, event: str):
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

    def run(self, step_id: str = None):
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        for step in steps:
            self.view_manager.handle_start(step.id)
            succeeded = self.try_execute_step_event(step, "on_start")
            if not succeeded:
                return
        self.setup_dataloader(steps)
        self.pause_event.clear()
        dag_is_active = True
        try:
            while (
                dag_is_active
                and not self.pause_event.is_set()
                and not self.close_event.is_set()
            ):
                dag_is_active = self.handle_steps(steps)
        finally:
            self.view_manager.handle_end()
            for step in steps:
                self.try_execute_step_event(step, "on_end")

    def step(self, step_id: str = None):
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        for step in steps:
            self.view_manager.handle_start(step.id)
            succeeded = self.try_execute_step_event(step, "on_start")
            if not succeeded:
                return
        self.setup_dataloader(steps)
        self.pause_event.clear()
        try:
            self.step_until_received_output(steps, step_id)
        finally:
            self.view_manager.handle_end()
            for step in steps:
                self.try_execute_step_event(step, "on_end")

    def set_is_running(self, is_running: bool = True, filename: str | None = None):
        self.is_running = is_running
        if filename is not None:
            self.filename = filename
        run_state = {"is_running": is_running, "filename": self.filename}
        self.view_manager.set_state("run_state", run_state)

    def try_update_state(self, local_graph: dict) -> bool:
        try:
            self.graph_state.update_state(
                local_graph["graph"], local_graph["resources"]
            )
            return True
        except NodeInstantiationError as e:
            traceback.print_exc()
            self.view_manager.handle_log(e.node_id, str(e), "error")
        except Exception as e:
            traceback.print_exc()
        return False

    def _exec(self, work: dict):
        self.set_is_running(True, work["filename"])
        if not self.try_update_state(work):
            return

        if work["cmd"] == "run_all":
            self.run()
        elif work["cmd"] == "run":
            self.run(work["step_id"])
        elif work["cmd"] == "step":
            self.step(work["step_id"])

    def start_loop(self):
        ExecutionContext.update(view_manager=self.view_manager)
        exec_cmds = ["run_all", "run", "step"]
        while not self.close_event.is_set():
            self.set_is_running(False)
            try:
                work = self.cmd_queue.get(timeout=MP_WORKER_TIMEOUT)
                if work["cmd"] in exec_cmds:
                    self._exec(work)
                elif work["cmd"] == "clear":
                    self.graph_state.clear_outputs(work.get("node_id"))
                    self.view_manager.handle_clear(work.get("node_id"))
                    step = self.graph_state.get_step(work.get("node_id"))
            except queue.Empty:
                pass
            except KeyboardInterrupt:
                break
            except Exception as e:
                break

    def start(self):
        self.thread.start()

    def stop(self):
        self.close_event.set()

    def exec(self, work: dict):
        self.cmd_queue.put(work)

    def get_output_note(self, step_id: str, pin_id: str, index: int) -> Note | None:
        output = self.graph_state.get_output_note(step_id, pin_id, index)
        return transform_json_log(output)

    def get_running_state(self):
        return self.is_running

    def handle_prompt_response(self, step_id: str, response: str) -> bool:
        return self.graph_state.handle_prompt_response(step_id, response)

    def pause(self):
        self.pause_event.set()

from ..steps import (
    Step,
    SourceStep,
    GeneratorSourceStep,
    AsyncStep,
    BatchStep,
    StepOutput,
    log,
)
from ..dataloading import Dataloader
from ..utils import MP_WORKER_TIMEOUT, transform_json_log, ExecutionContext
from .state import GraphState, StepState, NodeInstantiationError
from .event_handler import MemoryEventHandler
from ..shm import MultiThreadedMemoryManager
from typing import List, Optional, Any, Dict
from pathlib import Path
import queue
import multiprocessing as mp
import threading as th
import traceback
import time
import copy
import cloudpickle
from PIL import Image

step_output_err_res = "Step output must be a dictionary, and dict values must be lists."


class WebInstanceProcessor:
    def __init__(
        self,
        close_event: Optional[mp.Event],
        view_manager_queue: mp.Queue,
        continue_on_failure: bool,
        copy_outputs: bool,
        workflow_path: Path,
        custom_nodes_path: Path,
        spawn: bool,
        num_workers: int = 1,
    ):
        self.cmd_queue = mp.Queue()
        self.view_manager_queue = view_manager_queue
        self.workflow_path = workflow_path
        self.graph_state = GraphState(custom_nodes_path)
        self.continue_on_failure = continue_on_failure
        self.copy_outputs = copy_outputs
        self.num_workers = num_workers
        self.dataloader = Dataloader(self.num_workers, spawn)
        self.close_event = close_event if close_event is not None else mp.Event()
        self.pause_event = mp.Event()
        self.filename = None
        self.event_handler = None
        self.viewer = None
        self.thread = th.Thread(target=self.start_loop, daemon=True)

    def handle_images(self, outputs: StepOutput):
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
    ) -> Optional[StepOutput]:
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
            error_msg = f"{type(e).__name__}: {str(e)}"
            log(error_msg, "error")
            self.event_handler.write_log(step.id, error_msg, "error")
            traceback.print_exc()
            return None

        if outputs:
            if not isinstance(outputs, dict):
                if not len(step.Outputs) == 1:
                    error_msg = f"{step_output_err_res} Output was not a dict. This step has multiple outputs {step.Outputs} and cannot assume a single value."
                    log(error_msg, "error")
                    self.event_handler.write_log(step.id, error_msg, "error")
                    return None
                outputs = {step.Outputs[0]: outputs}

            for k, v in outputs.items():
                if not isinstance(v, list):
                    outputs[k] = [v]

            self.handle_images(outputs)
            self.graph_state.handle_outputs(
                step.id, outputs if not self.copy_outputs else copy.deepcopy(outputs)
            )

            self.event_handler.handle_time(step.id, time.time() - start_time)

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
            and not self.dataloader.is_failed()
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
        resource_values = self.graph_state.get_resource_values()
        for resource_id, value in resource_values.items():
            self.event_handler.handle_output(resource_id, "resource", value)

        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        for step in steps:
            self.event_handler.handle_start(step.id)
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
                and not self.dataloader.is_failed()
            ):
                dag_is_active = self.handle_steps(steps)
        finally:
            self.event_handler.handle_end()
            self.dataloader.stop()
            for step in steps:
                self.try_execute_step_event(step, "on_end")

    def step(self, step_id: str = None):
        resource_values = self.graph_state.get_resource_values()
        for resource_id, value in resource_values.items():
            self.event_handler.handle_output(resource_id, "resource", value)

        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        for step in steps:
            self.event_handler.handle_start(step.id)
            succeeded = self.try_execute_step_event(step, "on_start")
            if not succeeded:
                return

        self.setup_dataloader(steps)
        self.pause_event.clear()
        try:
            self.step_until_received_output(steps, step_id)
        finally:
            self.event_handler.handle_end()
            self.dataloader.stop()
            for step in steps:
                self.try_execute_step_event(step, "on_end")

    def set_is_running(self, is_running: bool = True, filename: Optional[str] = None):
        if filename is None and is_running:
            raise ValueError(
                "Filename must be provided when setting is_running to True"
            )
        self.filename = filename
        if is_running:
            # Create a new event handler for this run
            self.event_handler = MemoryEventHandler(filename, self.view_manager_queue)
            # Initialize the viewer
            self.viewer = self.event_handler.initialize_viewer()
            # Set up the execution context and graph state
            ExecutionContext.update(event_handler=self.event_handler)
            self.graph_state.set_viewer(self.viewer)
        else:
            # Mark execution as finished
            if self.event_handler:
                self.event_handler.handle_end()

    def cleanup(self):
        self.dataloader.shutdown()
        if self.event_handler:
            self.event_handler.cleanup()

    def setup_dataloader(self, steps: List[Step]):
        dataloader_consumers = [step for step in steps if isinstance(step, BatchStep)]
        consumer_ids = [id(c) for c in dataloader_consumers]
        consumer_load_fn = [
            c.load_fn if hasattr(c, "load_fn") else None for c in dataloader_consumers
        ]
        consumer_dump_fn = [
            c.dump_fn if hasattr(c, "dump_fn") else None for c in dataloader_consumers
        ]
        self.dataloader.start(consumer_ids, consumer_load_fn, consumer_dump_fn)

    def try_update_state(self, work: dict) -> bool:
        try:
            filename: str = work["filename"]
            if filename.endswith(".py"):
                graph = cloudpickle.loads(work["graph"])
                self.graph_state.update_state_py(graph, work["params"])
            else:
                self.graph_state.update_state(work["graph"], work["resources"])
            return True
        except NodeInstantiationError as e:
            traceback.print_exc()
            self.event_handler.write_log(e.node_id, str(e), "error")
        except Exception as e:
            traceback.print_exc()
        return False

    def _exec(self, work: dict):
        self.set_is_running(True, work["filename"])
        try:
            if not self.try_update_state(work):
                return

            cmd: str = work["cmd"]
            if cmd == "run_all" or cmd == "py_run_all":
                self.run()
            elif cmd == "run" or cmd == "py_run":
                self.run(work["step_id"])
            elif cmd == "step" or cmd == "py_step":
                self.step(work["step_id"])
        finally:
            self.set_is_running(False)

    def start_loop(self):
        ExecutionContext.update(dataloader=self.dataloader)
        exec_cmds = ["run_all", "run", "step", "py_run_all", "py_run", "py_step"]
        while not self.close_event.is_set():
            try:
                work = self.cmd_queue.get(timeout=MP_WORKER_TIMEOUT)
                if work["cmd"] in exec_cmds:
                    self._exec(work)
                elif work["cmd"] == "clear":
                    self.graph_state.clear_outputs(work.get("node_id"))
                    if self.event_handler:
                        self.event_handler.handle_clear(work.get("node_id"))
                    step = self.graph_state.get_step(work.get("node_id"))
                    self.dataloader.clear(id(step) if step != None else None)
            except queue.Empty:
                pass
            except (OSError, EOFError, KeyboardInterrupt):
                self.cleanup()
                break
            except Exception as e:
                self.cleanup()
                if not self.close_event.is_set():
                    traceback.print_exc()
                break

    def start(self):
        self.thread.start()

    def stop(self):
        self.close_event.set()
        self.cleanup()
        if self.thread.is_alive():
            # self.thread.join()
            pass

    def exec(self, work: dict):
        self.cmd_queue.put(work)

    def get_worker_queue_sizes(self):
        return self.dataloader.get_all_sizes()

    def get_output(self, step_id: str, pin_id: str, index: int) -> Optional[Any]:
        output = self.graph_state.get_output(step_id, pin_id, index)
        return transform_json_log(output)

    def handle_prompt_response(self, step_id: str, response: str) -> bool:
        return self.graph_state.handle_prompt_response(step_id, response)

    def pause(self):
        self.pause_event.set()

    def get_queue(self):
        return self.cmd_queue

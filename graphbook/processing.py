from graphbook.steps import Step, SourceStep, AsyncStep
from graphbook.dataloading import Dataloader
from .note import Note
from typing import List
import queue
import multiprocessing as mp
import multiprocessing.connection as mpc
from graphbook.utils import MP_WORKER_TIMEOUT
from graphbook.state import GraphState, StepState
from graphbook.viewer import ViewManagerInterface
import traceback
import asyncio


class WebInstanceProcessor:
    def __init__(
        self,
        cmd_queue: mp.Queue,
        server_request_conn: mpc.Connection,
        view_manager_queue: mp.Queue,
        output_dir: str,
        custom_nodes_path: str,
        close_event: mp.Event,
        pause_event: mp.Event,
        num_workers: int = 1,
    ):
        self.cmd_queue = cmd_queue
        self.close_event = close_event
        self.pause_event = pause_event
        self.view_manager = ViewManagerInterface(view_manager_queue)
        self.graph_state = GraphState(custom_nodes_path, view_manager_queue, server_request_conn, close_event)
        self.output_dir = output_dir
        self.custom_nodes_path = custom_nodes_path
        self.num_workers = num_workers
        self.steps = {}
        self.dataloader = Dataloader(self.output_dir, self.num_workers)
        self.is_running = False

    def exec_step(self, step: Step, input: Note = None, flush: bool = False):
        outputs = {}
        step_fn = step if not flush else step.all
        try:
            if input is None:
                outputs = step_fn()
            else:
                if isinstance(step, AsyncStep):
                    outputs = step.in_q(input)
                else:
                    outputs = step_fn(input)
        except Exception as e:
            step.logger.log_exception(e)
            traceback.print_exc()
            return {}

        if outputs:
            self.graph_state.handle_outputs(step.id, outputs)
            self.view_manager.handle_outputs(step.id, outputs)
        return outputs

    def handle_steps(self, steps: List[Step]) -> bool:
        is_active = False
        for step in steps:
            output = None
            if isinstance(step, SourceStep):
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

            if not is_active and output:
                is_active = any(len(v) > 0 for v in output.values())

        return is_active

    def step_until_received_output(self, steps: List[Step], step_id: str):
        is_active = True
        step_executed = False
        while is_active and not step_executed and not self.pause_event.is_set():
            is_active = self.handle_steps(steps)
            step_executed = self.graph_state.get_state(step_id, StepState.EXECUTED_THIS_RUN)

    def run(self, step_id: str = None):
        self.is_running = True
        self.view_manager.handle_run_state(True)
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        self.setup_dataloader(steps)
        for step in steps:
            self.view_manager.handle_start(step.id)
            step.on_start()
        self.pause_event.clear()
        dag_is_active = True
        try:
            while dag_is_active and not self.pause_event.is_set():
                dag_is_active = self.handle_steps(steps)
        finally:
            self.view_manager.handle_end()
            for step in steps:
                step.on_end()

    def step(self, step_id: str = None):
        self.is_running = True
        self.view_manager.handle_run_state(True)
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        self.setup_dataloader(steps)
        for step in steps:
            self.view_manager.handle_start(step.id)
            step.on_start()
        self.pause_event.clear()
        try:
            self.step_until_received_output(steps, step_id)
        finally:
            self.view_manager.handle_end()
            for step in steps:
                step.on_end()

    def cleanup(self):
        self.dataloader.shutdown()

    def setup_dataloader(self, steps: List[Step]):
        dataloader_consumers = [step for step in steps if isinstance(step, AsyncStep)]
        self.dataloader.setup([id(c) for c in dataloader_consumers])
        for c in dataloader_consumers:
            c.set_dataloader(self.dataloader)

    def __str__(self):
        return self.root.__str__()
    
    def try_update_state(self, queue_entry: dict):
        try:
            self.graph_state.update_state(queue_entry["graph"], queue_entry["resources"])
        except Exception as e:
            traceback.print_exc()

    async def start_loop(self):
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self.graph_state.start_client_loop)
        print("IN PROCESSOR LOOP")
        while not self.close_event.is_set():
            if self.is_running:
                self.is_running = False
                self.view_manager.handle_run_state(False)
            try:
                work = self.cmd_queue.get(timeout=MP_WORKER_TIMEOUT)
                if work["cmd"] == "run_all":
                    self.try_update_state(work)
                    self.run()
                elif work["cmd"] == "run":
                    self.try_update_state(work)
                    self.run(work["step_id"])
                elif work["cmd"] == "step":
                    self.try_update_state(work)
                    self.step(work["step_id"])
                elif work["cmd"] == "clear":
                    self.try_update_state(work)
                    self.graph_state.clear_outputs(work.get("step_id"))
            except KeyboardInterrupt:
                self.cleanup()
                break
            except queue.Empty:
                pass

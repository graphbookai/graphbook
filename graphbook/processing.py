from graphbook.steps import Step, SourceStep, AsyncStep, StepOutput
from graphbook.dataloading import Dataloader
from .note import Note
from typing import List
import queue
import multiprocessing as mp
import multiprocessing.connection as mpc
from graphbook.utils import MP_WORKER_TIMEOUT, ProcessorStateRequest
from graphbook.state import GraphState, StepState, NodeInstantiationError
from graphbook.viewer import ViewManagerInterface
import traceback
import asyncio
import time


class WebInstanceProcessor:
    def __init__(
        self,
        cmd_queue: mp.Queue,
        server_request_conn: mpc.Connection,
        view_manager_queue: mp.Queue,
        output_dir: str,
        continue_on_failure: bool,
        custom_nodes_path: str,
        close_event: mp.Event,
        pause_event: mp.Event,
        num_workers: int = 1,
    ):
        self.cmd_queue = cmd_queue
        self.close_event = close_event
        self.pause_event = pause_event
        self.view_manager = ViewManagerInterface(view_manager_queue)
        self.graph_state = GraphState(custom_nodes_path, view_manager_queue)
        self.output_dir = output_dir
        self.continue_on_failure = continue_on_failure
        self.custom_nodes_path = custom_nodes_path
        self.num_workers = num_workers
        self.steps = {}
        self.dataloader = Dataloader(self.num_workers)
        self.state_client = ProcessorStateClient(
            server_request_conn, close_event, self.graph_state, self.dataloader
        )
        self.is_running = False
        self.filename = None

    def exec_step(
        self, step: Step, input: Note | None = None, flush: bool = False
    ) -> StepOutput | None:
        outputs = {}
        step_fn = step if not flush else step.all
        start_time = time.time()
        try:
            if input is None:
                outputs = step_fn()
            else:
                if isinstance(step, AsyncStep):
                    step.in_q(input)
                else:
                    outputs = step_fn(input)
        except Exception as e:
            step.logger.log_exception(e)
            traceback.print_exc()
            return None

        if outputs is not None:
            self.graph_state.handle_outputs(step.id, outputs)
            self.view_manager.handle_outputs(step.id, outputs)
        self.view_manager.handle_time(step.id, time.time() - start_time)
        return outputs

    def handle_steps(self, steps: List[Step]) -> bool:
        is_active = False
        for step in steps:
            output = {}
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
            and not self.dataloader.is_failed()
        ):
            is_active = self.handle_steps(steps)
            step_executed = self.graph_state.get_state(
                step_id, StepState.EXECUTED_THIS_RUN
            )

    def run(self, step_id: str = None):
        steps: List[Step] = self.graph_state.get_processing_steps(step_id)
        self.setup_dataloader(steps)
        for step in steps:
            self.view_manager.handle_start(step.id)
            step.on_start()
        self.pause_event.clear()
        dag_is_active = True
        try:
            while (
                dag_is_active
                and not self.pause_event.is_set()
                and not self.dataloader.is_failed()
            ):
                dag_is_active = self.handle_steps(steps)
        finally:
            self.view_manager.handle_end()
            for step in steps:
                step.on_end()

    def step(self, step_id: str = None):
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

    def set_is_running(self, is_running: bool = True, filename: str | None = None):
        self.is_running = is_running
        if filename is not None:
            self.filename = filename
        run_state = {"is_running": is_running, "filename": self.filename}
        self.view_manager.handle_run_state(run_state)
        self.state_client.set_running_state(run_state)

    def cleanup(self):
        self.dataloader.shutdown()

    def setup_dataloader(self, steps: List[Step]):
        dataloader_consumers = [step for step in steps if isinstance(step, AsyncStep)]
        consumer_ids = [id(c) for c in dataloader_consumers]
        consumer_load_fn = [
            c.load_fn if hasattr(c, "load_fn") else None for c in dataloader_consumers
        ]
        consumer_dump_fn = [
            c.dump_fn if hasattr(c, "dump_fn") else None for c in dataloader_consumers
        ]
        self.dataloader.setup(consumer_ids, consumer_load_fn, consumer_dump_fn)
        for c in dataloader_consumers:
            c.set_dataloader(self.dataloader)

    def try_update_state(self, queue_entry: dict) -> bool:
        try:
            self.graph_state.update_state(
                queue_entry["graph"], queue_entry["resources"]
            )
            return True
        except NodeInstantiationError as e:
            traceback.print_exc()
            self.view_manager.handle_log(e.node_id, str(e), "error")
        except Exception as e:
            traceback.print_exc()
        return False

    async def start_loop(self):
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self.state_client.start)
        while not self.close_event.is_set():
            self.set_is_running(False)
            try:
                work = self.cmd_queue.get(timeout=MP_WORKER_TIMEOUT)
                if work["cmd"] == "run_all":
                    self.set_is_running(True, work["filename"])
                    if self.try_update_state(work):
                        self.run()
                elif work["cmd"] == "run":
                    self.set_is_running(True, work["filename"])
                    if self.try_update_state(work):
                        self.run(work["step_id"])
                elif work["cmd"] == "step":
                    self.set_is_running(True, work["filename"])
                    if self.try_update_state(work):
                        self.step(work["step_id"])
                elif work["cmd"] == "clear":
                    if self.try_update_state(work):
                        self.graph_state.clear_outputs(work.get("step_id"))
                        self.view_manager.handle_clear(work.get("step_id"))
                        self.dataloader.clear()
            except KeyboardInterrupt:
                self.cleanup()
                break
            except queue.Empty:
                pass


class ProcessorStateClient:
    def __init__(
        self,
        server_request_conn: mpc.Connection,
        close_event: mp.Event,
        graph_state: GraphState,
        dataloader: Dataloader,
    ):
        self.server_request_conn = server_request_conn
        self.close_event = close_event
        self.curr_task = None
        self.graph_state = graph_state
        self.dataloader = dataloader
        self.running_state = {}

    def _loop(self):
        while not self.close_event.is_set():
            if self.server_request_conn.poll(timeout=MP_WORKER_TIMEOUT):
                req = self.server_request_conn.recv()
                if req["cmd"] == ProcessorStateRequest.GET_OUTPUT_NOTE:
                    step_id = req.get("step_id")
                    pin_id = req.get("pin_id")
                    index = req.get("index")
                    if step_id is None or pin_id is None or index is None:
                        output = {}
                    else:
                        output = self.graph_state.get_output_note(
                            step_id, pin_id, index
                        )
                elif req["cmd"] == ProcessorStateRequest.GET_WORKER_QUEUE_SIZES:
                    output = self.dataloader.get_all_sizes()
                elif req["cmd"] == ProcessorStateRequest.GET_RUNNING_STATE:
                    output = self.running_state
                else:
                    output = {}
                entry = {"res": req["cmd"], "data": output}
                self.server_request_conn.send(entry)

    def start(self):
        self._loop()

    def close(self):
        if self.curr_task is not None:
            self.curr_task.cancel()

    def set_running_state(self, state: dict):
        self.running_state = state


def poll_conn_for(
    conn: mpc.Connection, req: ProcessorStateRequest, body: dict = None
) -> dict:
    req_data = {"cmd": req}
    if body:
        req_data.update(body)
    conn.send(req_data)
    if conn.poll(timeout=MP_WORKER_TIMEOUT):
        res = conn.recv()
        if res.get("res") == req:
            return res.get("data")
    return {}

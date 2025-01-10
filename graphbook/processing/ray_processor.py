from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING

import logging
from dataclasses import dataclass
from ray import ObjectRef
from ..steps import (
    StepOutput as Outputs,
)
from ..utils import MP_WORKER_TIMEOUT, transform_json_log, ExecutionContext
from ..note import Note
from typing import List
import ray._raylet
import ray
from graphbook.viewer import ViewManagerInterface

from ray.workflow.common import (
    TaskID,
)
import graphbook.web

if TYPE_CHECKING:
    from graphbook.processing.ray_api import GraphbookTaskContext
    from graphbook.clients import ClientPool, Client

logger = logging.getLogger(__name__)

step_output_err_res = (
    "Step output must be a dictionary, and dict values must be lists of notes."
)


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


@ray.remote(name="_graphbook_RayStepHandler")
class RayStepHandler:
    def __init__(self, view_manager_queue):
        self.graph_state = RayExecutionState()
        self.view_manager = ViewManagerInterface(view_manager_queue)

    def init_step(self):
        return self.graph_state.init_step()
    
    def handle_new_execution(self, name: str):
        self.view_manager.set_state("run_state", {"is_running": True, "filename": name})
        
    def handle_end_execution(self, name: str):
        self.view_manager.set_state("run_state", {"is_running": False, "filename": name})

    def handle_log(self, node_id, msg, type):
        self.view_manager.handle_log(node_id, msg, type)

    def handle(
        self, step_id: str, *bind_args: List[Tuple[str, dict]]
    ) -> Optional[List[Note]]:
        all_notes = []
        for i in range(0, len(bind_args), 2):
            bind_key, outputs = bind_args[i], bind_args[i + 1]
            for note in outputs[bind_key]:
                if not isinstance(note, Note):
                    # log
                    print(
                        f"{step_output_err_res} Output was not a Note.",
                        "error",
                    )
                    return None
            all_notes.extend(outputs[bind_key])
            self.graph_state.handle_outputs(step_id, outputs)
        return all_notes


class RayExecutionState:
    def __init__(self):
        self.curr_idx = 0
        self.steps_outputs: Dict[str, DictionaryArrays] = {}
        self.handled_steps = set()

    def init_step(self):
        idx = str(self.curr_idx)
        self.curr_idx += 1
        self.steps_outputs[idx] = DictionaryArrays()
        return idx

    def get_iterator(self, step_id: str, label: str):
        for note in self.steps_outputs[step_id][label]:
            yield note

    def handle_outputs(self, step_id: str, outputs: Outputs):
        assert step_id in self.steps_outputs, f"Step {step_id} not initialized"
        if step_id in self.handled_steps:
            return
        self.handled_steps.add(step_id)
        for label, notes in outputs.items():
            self.steps_outputs[step_id].enqueue(label, notes)

        # self.view_manager.handle_queue_size(
        #     step_id, self.steps_outputs[step_id].sizes()
        # )
        # self.view_manager.handle_outputs(step_id, transform_json_log(outputs))


class DictionaryArrays:
    def __init__(self):
        self._dict: Dict[str, list] = {}

    def enqueue(self, label: str, notes: List[Note]):
        if label not in self._dict:
            self._dict[label] = []
        self._dict[label].extend(notes)

    def __getitem__(self, label: str):
        return self._dict[label]

    def sizes(self):
        return {k: len(v) for k, v in self._dict.items()}

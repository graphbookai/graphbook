from graphbook.steps.base import Step
from graphbook.note import Note
import multiprocessing as mp

class RemoteReadStep(Step):
    def __init__(self, id, logger, queue: mp.Queue):
        super().__init__(id, logger)
        self._queue = queue

    def __call__(self, note: Note):
        if self._queue.empty():
            return {}
        step_id, note = self._queue.get(False)
        return {step_id: note}


class RemoteWriteStep(Step):
    def __init__(self, id, logger, queue: mp.Queue):
        super().__init__(id, logger)
        self._queue = queue

    def dequeue_note(self) -> Note | None:
        if self._queue.empty():
            return None
        return self._queue.get(False)

    def __call__(self, note: Note):
        self._queue.put(note)

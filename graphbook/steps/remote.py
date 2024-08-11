from graphbook.steps.base import Step
from graphbook.note import Note
import queue


class RemoteReadStep(Step):
    def __init__(self, id, logger):
        super().__init__(id, logger)
        self._queue = queue.Queue()

    def enqueue_note(self, step_id: str, note: Note):
        self._queue.put((step_id, note))

    def __call__(self, note: Note):
        if self._queue.empty():
            return {}
        step_id, note = self._queue.get(False)
        return {step_id: note}


class RemoteWriteStep(Step):
    def __init__(self, id, logger):
        super().__init__(id, logger)
        self._queue = queue.Queue()

    def dequeue_note(self) -> Note | None:
        if self._queue.empty():
            return None
        return self._queue.get(False)

    def __call__(self, note: Note):
        self._queue.put(note)

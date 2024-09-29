from __future__ import annotations
from typing import List, Dict, Tuple, Generator, Any
from graphbook import Note
from graphbook.utils import (
    transform_function_string,
    convert_dict_values_to_list,
    is_batchable,
)
from graphbook.logger import log, prompt
import graphbook.prompts as prompts
import graphbook.dataloading as dataloader
import warnings
import traceback

warnings.simplefilter("default", DeprecationWarning)

StepOutput = Dict[str, List[Note]]
"""A dict mapping of output slot to Note list. Every Step outputs a StepOutput."""


class Step:
    """
    The base class of the executable workflow node, step. All other step classes should be a descendant of this class.
    """

    def __init__(self, item_key=None):
        self.id = None
        self.item_key = item_key
        self.parents = []
        self.children = {"out": []}

    def set_child(self, child: Step, slot_name: str = "out"):
        """
        Sets a child step

        Args:
            child (Step): child step
            slot_name (str): slot to bind the child to
        """
        if self not in child.parents:
            child.parents.append(self)
        if slot_name not in self.children:
            self.children[slot_name] = []
        if child not in self.children[slot_name]:
            self.children[slot_name].append(child)

    def remove_children(self):
        """
        Removes all children steps
        """
        for children in self.children.values():
            for child in children:
                if self in child.parents:
                    child.parents.remove(self)
        self.children = {}

    def log(self, message: str, type: str = "info"):
        """
        Logs a message

        Args:
            message (str): message to log
            type (str): type of log
        """
        log(message, type)

    def on_start(self):
        """
        Executes upon start of graph execution
        """
        pass

    def on_end(self):
        """
        Executes upon end of graph execution
        """
        pass

    def on_note(self, note: Note):
        """
        Executes upon receiving a Note

        Args:
            note (Note): The Note input
        """
        pass

    def on_after_item(self, note: Note):
        """
        Executes upon receiving a Note and after processing items

        Args:
            note (Note): The Note input
        """
        pass

    def on_item(self, item: Any, note: Note):
        """
        Executes upon receiving an item. Is called after *on_note()* and before *on_after_item()*.

        Args:
            item (Any): The item to process
            note (Note): The Note that the item belongs to
        """
        pass

    def on_clear(self):
        """
        Executes when a request to clear the step is made. This is useful for steps that have internal states that need to be reset.
        """
        pass

    def forward_note(self, note: Note) -> str | StepOutput:
        """
        Routes a Note. Must return the corresponding output key or a dictionary that contains Notes.
        Is called after *on_after_item()*.

        Args:
            note (Note): The Note input

        Returns:
            A string that the note is associated with, or if multiple notes are being processed at a time, a StepOutput may be used.
        """
        return "out"

    def __call__(self, note: Note) -> StepOutput:
        # 1. on_note -> 2. on_item -> 3. on_after_item -> 4. forward_note
        self.on_note(note)

        if self.item_key is not None:
            item = note.items.get(self.item_key, None)
            assert (
                item is not None
            ), f"Item key {self.item_key} not found in Note. Cannot retrieve any iterable."
            self.on_item(item, note)

        self.on_after_item(note)

        out = self.forward_note(note)
        output = {}
        if isinstance(out, str):
            output[out] = [note]
        elif isinstance(out, dict):
            output = out
        return output

    def all(self, notes: List[Note]) -> StepOutput:
        step_outputs = []
        if notes is not None:
            for note in notes:
                step_output = self(note)
                if step_output is not None:
                    step_outputs.append(step_output)

        if len(step_outputs) == 0:
            return {}

        output_keys = step_outputs[0].keys()
        return {
            k: [note for step_output in step_outputs for note in step_output.get(k, [])]
            for k in output_keys
        }

    def __str__(self):
        def get_str(step, indent):
            s = f"{' ' * indent}({step.id}) {type(step).__name__}\n"
            for child in step.children.values():
                for c in child:
                    s += get_str(c, indent + 2)
            return s

        return get_str(self, 0)


class SourceStep(Step):
    """
    A Step that accepts no input but produce outputs.
    This this class will attempt to load all data at once, so it is recommended to use GeneratorSourceStep especially for large datasets.
    """

    def __init__(self):
        super().__init__()

    def load(self) -> StepOutput:
        """
        Function to load data and convert into Notes. Must output a dictionary of Notes.
        """
        raise NotImplementedError("load function must be implemented for SourceStep")

    def __call__(self):
        result = self.load()
        convert_dict_values_to_list(result)
        return result


class GeneratorSourceStep(SourceStep):
    """
    A Step that accepts no input but produce outputs.
    """

    def __init__(self):
        super().__init__()
        self.generator = self.load()

    def load(self) -> Generator[StepOutput, None, None]:
        """
        Function to load data and convert into Notes. Must output a generator that yields a dictionary of Notes.
        """
        raise NotImplementedError("load function must be implemented for SourceStep")

    def on_clear(self):
        self.generator = self.load()

    def __call__(self):
        try:
            return next(self.generator)
        except StopIteration:
            return {}


class AsyncStep(Step):
    """
    Asynchronous processing step that will consume everything in the in_queue so that the main thread can handle the outputs.
    Useful for parallel processing where the task can be optimized with multiple processes and the main thread can continue
    processing the rest of the graph.
    """

    def __init__(self, item_key=None):
        super().__init__(item_key)
        self._in_queue = []
        self._out_queue = []

    def on_clear(self):
        self._in_queue = []
        self._out_queue = []

    def in_q(self, note: Note | None):
        if note is None:
            return
        self._in_queue.append(note)

    def is_active(self) -> bool:
        return len(self._in_queue) > 0

    def __call__(self) -> StepOutput:
        # 1. on_note -> 2. on_item -> 3. on_after_item -> 4. forward_note
        if len(self._out_queue) == 0:
            return {}
        note = self._out_queue.pop(0)
        return super().__call__(note)

    def all(self) -> StepOutput:
        return self.__call__()


class NoteItemHolders:
    def __init__(self):
        self.item_counts = {}
        self.notes = {}
        self.completed_notes = {}

    def handle_note(self, note: Note):
        note_id = id(note)
        if note_id not in self.notes:
            self.notes[note_id] = note
        if note_id not in self.item_counts:
            self.item_counts[note_id] = 0
        self.item_counts[note_id] += 1

    def handle_item(self, note_id):
        self.item_counts[note_id] -= 1

    def set_completed(self, note: Note):
        note_id = id(note)
        self.completed_notes[note_id] = note
        if note_id not in self.item_counts:
            self.item_counts[note_id] = 0

    def pop_all_completed(self):
        completed = []
        to_remove = []
        for note_id in self.completed_notes:
            if self.item_counts[note_id] == 0:
                completed.append(self.completed_notes[note_id])
                to_remove.append(note_id)
                del self.item_counts[note_id]
        for note_id in to_remove:
            del self.completed_notes[note_id]
        return completed

    def is_active(self):
        return len(self.completed_notes) > 0


StepData = Tuple[List[Any], List[Note], List[Note]]


class BatchStep(AsyncStep):
    """
    A Step used for batch processing. This step will consume Pytorch tensor batches loaded by the worker pool by default.
    """

    def __init__(self, batch_size, item_key):
        super().__init__(item_key=item_key)
        self.batch_size = int(batch_size)
        self.loaded_notes = {}
        self.num_loaded_notes = {}
        self.dumped_item_holders = NoteItemHolders()
        self.accumulated_items = [[], [], []]
        self._c = 0
        self._d = {}

    def in_q(self, note: Note | None):
        """
        Enqueue a note to be processed by the step

        Args:
            note (Note): The Note input
        """
        if note is None:
            return
        self.on_note(note)
        items = note[self.item_key]
        if items is None:
            raise ValueError(f"Item key {self.item_key} not found in Note.")

        # Load
        if hasattr(self, "load_fn"):
            note_id = id(note)
            if not is_batchable(items):
                items = [items]

            if len(items) > 0:
                dataloader.put_load(items, note_id, id(self))
                self.loaded_notes[note_id] = note
                self.num_loaded_notes[note_id] = len(items)

    def on_clear(self):
        self.loaded_notes = {}
        self.num_loaded_notes = {}
        self.dumped_item_holders = NoteItemHolders()
        self.accumulated_items = [[], [], []]

    def get_batch(self, flush: bool = False) -> StepData:
        items, notes, completed = self.accumulated_items
        next_in = dataloader.get_load(id(self))
        if next_in is not None:
            item, note_id = next_in
            # get original note (not pickled one)
            note = self.loaded_notes[note_id]
            if item is not None:
                items.append(item)
                notes.append(note)
            remaining_items = self.num_loaded_notes[note_id] - 1
            if remaining_items > 0:
                self.num_loaded_notes[note_id] = remaining_items
            else:
                del self.num_loaded_notes[note_id]
                del self.loaded_notes[note_id]
                completed.append(note)
        else:
            if len(self.accumulated_items[0]) == 0:
                return None

        if len(items) == 0:
            return None
        if len(items) < self.batch_size:
            if not flush:
                return None
            else:
                if len(self.loaded_notes) > 0:
                    return None

        batch = (items[: self.batch_size], notes[: self.batch_size], completed)
        self.accumulated_items = (
            items[self.batch_size :],
            notes[self.batch_size :],
            [],
        )
        return batch

    def dump_data(self, note: Note, output):
        """
        Dumps data to be processed by the worker pool. This is called after the step processes the batch of items.
        The class must have a dump_fn method that takes in the output data and returns a string path to the dumped data.

        Args:
            note (Note): The Note input
            item_key (str): The item key to dump
            output (Any): The output data to dump
        """
        self.dumped_item_holders.handle_note(note)
        dataloader.put_dump(output, id(note), id(self))

    @staticmethod
    def dump_fn(**args):
        """
        The dump function to be overriden by BatchSteps that write outputs to disk.
        """
        raise NotImplementedError(
            "dump_fn must be implemented for BatchStep when using the worker pool to dump outputs"
        )

    @staticmethod
    def load_fn(**args):
        """
        The load function to be overriden by BatchSteps that will forward preprocessed data to `on_item_batch`.
        """
        raise NotImplementedError(
            "load_fn must be implemented for BatchStep when using the worker pool to load inputs"
        )

    def handle_batch(self, batch: StepData):
        loaded, notes, completed = batch
        outputs = [l[0] for l in loaded]
        indexes = [l[1] for l in loaded]

        items = []
        for note, index in zip(notes, indexes):
            item = note.items[self.item_key]
            if is_batchable(item):
                items.append(item[index])
            else:
                items.append(item)

        data_dump = self.on_item_batch(outputs, items, notes)
        if data_dump is not None:
            if isinstance(data_dump, dict):
                # Dict returns are deprecated
                warnings.warn(
                    "dict returns for on_item_batch are deprecated and will be removed in a future version. Please return a list of your parameter tuples to provide to dump_fn instead.",
                    DeprecationWarning,
                )
                for k, v in data_dump.items():
                    if len(notes) != len(v):
                        self.log(
                            f"Unexpected number of notes ({len(notes)}) does not match returned outputs ({len(v)}). Will not write outputs!"
                        )
                    else:
                        for note, out in zip(notes, v):
                            self.dump_data(note, out)
            else:
                for note, out in zip(notes, data_dump):
                    self.dump_data(note, out)

        for note in completed:
            self.dumped_item_holders.set_completed(note)

    def handle_completed_notes(self):
        note_id = dataloader.get_dump(id(self))
        if note_id is not None:
            self.dumped_item_holders.handle_item(note_id)
        output = {}
        for note in self.dumped_item_holders.pop_all_completed():
            self.on_after_item(note)
            output_key = self.forward_note(note)
            if output_key not in output:
                output[output_key] = []
            output[output_key].append(note)
        return output

    def on_item_batch(self, outputs, items, notes) -> List[Tuple[Any]] | None:
        """
        Called when B items are loaded and are ready to be processed where B is *batch_size*. This is meant to be overriden by subclasses.

        Args:
            outputs (List[Any]): The list of loaded outputs of length B
            items (List[Any]): The list of anys of length B associated with outputs. This list has the same order as outputs does
                along the batch dimension
            notes (List[Note]): The list of Notes of length B associated with outputs. This list has the same order as outputs does
                along the batch dimension

        Returns:
            List[Tuple[Any]] | None: The output data to be dumped as a list of parameters to be passed to dump_fn. If None is returned, nothing will be dumped.
        """
        pass

    def __call__(self, flush: bool = False):
        """
        Batches input and executes the step if accumulated batch is equal to batch_size. Returns true if step is executed.

        Args:
            flush (bool): If True, will force the step to execute even if the batch size is not met
        """
        batch = self.get_batch(flush)
        if batch:
            self.handle_batch(batch)

        output = self.handle_completed_notes()
        return output

    def all(self) -> StepOutput:
        outputs = {}
        has_outputs = True
        while has_outputs:
            out = self(flush=True)
            for k, v in out.items():
                if k not in outputs:
                    outputs[k] = []
                outputs[k].extend(v)
            has_outputs = len(out) > 0
        return outputs

    def is_active(self) -> bool:
        return (
            len(self.loaded_notes) > 0
            or len(self.accumulated_items[0]) > 0
            or self.dumped_item_holders.is_active()
        )


class PromptStep(AsyncStep):
    """
    A Step that is capable of prompting the user for input.
    This is useful for interactive workflows where data labeling, model evaluation, or any other human input is required.
    Once the prompt is handled, the execution lifecycle of the Step will proceed, normally.
    """
    def __init__(self):
        super().__init__()
        self._is_awaiting_response = False
        self._awaiting_note = None

    def handle_prompt_response(self, response: Any):
        note = self._awaiting_note
        try:
            assert note is not None, "PromptStep is not awaiting a response."
            self.on_prompt_response(note, response)
            self._out_queue.append(note)
        except Exception as e:
            self.log(f"{type(e).__name__}: {str(e)}", "error")
            traceback.print_exc()

        self._is_awaiting_response = False
        self._awaiting_note = None
        prompt(prompts.none())

    def on_clear(self):
        """
        Clears any awaiting prompts and the prompt queue.
        If you plan on overriding this method, make sure to call super().on_clear() to ensure the prompt queue is cleared.
        """
        self._is_awaiting_response = False
        self._awaiting_note = None
        prompt(prompts.none())
        super().on_clear()

    def get_prompt(self, note: Note) -> dict:
        """
        Returns the prompt to be displayed to the user.
        This method can be overriden by the subclass.
        By default, it will return a boolean prompt.
        If None is returned, the prompt will be skipped on this note.
        A list of available prompts can be found in ``graphbook.prompts``.
        
        Args:
            note (Note): The Note input to display to the user
        """
        return prompts.bool_prompt(note)

    def on_prompt_response(self, note: Note, response: Any):
        """
        Called when the user responds to the prompt.
        This method must be overriden by the subclass.

        Args:
            note (Note): The Note input that was prompted
            response (Any): The user's response
        """
        raise NotImplementedError(
            "on_prompt_response must be implemented for PromptStep"
        )

    def __call__(self):
        if not self._is_awaiting_response and len(self._in_queue) > 0:
            note = self._in_queue.pop(0)
            p = self.get_prompt(note)
            if p:
                prompt(self.get_prompt(note))
                self._is_awaiting_response = True
                self._awaiting_note = note
            else:
                self._out_queue.append(note)
        return super().__call__()

    def is_active(self) -> bool:
        return len(self._in_queue) > 0 or self._awaiting_note is not None


class Split(Step):
    """
    Routes incoming Notes into either of two output slots, A or B. If split_fn
    evaluates to True, the note will be forwarded to A, else the note will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *forward_note(note)* where each note is fed into *split_fn(note)*.
    """

    RequiresInput = True
    Parameters = {"split_fn": {"type": "resource"}}
    Outputs = ["A", "B"]
    Category = "Filtering"

    def __init__(self, split_fn):
        super().__init__()
        self.split_fn = split_fn
        self.fn = transform_function_string(split_fn)

    def forward_note(self, note) -> str:
        split_result = self.fn(note=note)
        if split_result:
            return "A"
        return "B"


class SplitNotesByItems(Step):
    """
    Routes incoming Notes into either of two output slots, A or B. If split_fn evaluates to True,
    the note will be forwarded to A, else the note will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *forward_note(note)* where each note and selected items is fed into \
        *split_fn(items, notes)*.
    """

    RequiresInput = True
    Parameters = {
        "split_items_fn": {"type": "resource"},
        "item_key": {"type": "string"},
    }
    Outputs = ["A", "B"]
    Category = "Filtering"

    def __init__(self, split_items_fn, item_key):
        super().__init__(item_key=item_key)
        self.split_fn = split_items_fn
        self.fn = transform_function_string(split_items_fn)

    def forward_note(self, note: Note) -> StepOutput:
        split_result = self.fn(items=note.items[self.item_key], note=note)
        if split_result:
            return "A"
        return "B"


class SplitItemField(Step):
    """
    Associates items with a different item key based on the *split_fn(item)*. If split_fn evaluates to True,
    the item will transfer to the item_key specified by a_key, else the item will transfer to the item_key
    specified by b_key.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *on_after_item(note)* where each selected item from item_key is fed into \
        *split_fn(item)*.
        item_key (str): Original item_key that the items come from
        a_key (str): Will append item to any list associated with the a_key if *split_fn(item)* evaluates to True
        b_key (str): Will append item to any list associated with the b_key if *split_fn(item)* evaluates to False
        should_delete_original (str): If True, will delete original any key-value pair of item_key. Defaults to True
        
    """

    RequiresInput = True
    Parameters = {"split_fn": {"type": "resource"}, "item_key": {"type": "string"}}
    Category = "Filtering"
    Outputs = ["out"]

    def __init__(self, split_fn, item_key, a_key, b_key, should_delete_original=True):
        super().__init__(item_key=item_key)
        self.split_fn = split_fn
        self.fn = transform_function_string(split_fn)
        self.a_key = a_key
        self.b_key = b_key
        self.should_delete_original = should_delete_original

    def on_after_item(self, note: Note) -> StepOutput:
        a_items = []
        b_items = []
        for item in note.items[self.item_key]:
            if self.fn(item=item):
                a_items.append(item)
            else:
                b_items.append(item)
        note.items[self.a_key] = a_items
        note.items[self.b_key] = b_items
        if self.should_delete_original:
            del note.items[self.item_key]

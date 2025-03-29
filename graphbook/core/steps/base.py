from __future__ import annotations
from typing import (
    List,
    Dict,
    Tuple,
    Generator,
    Any,
    Literal,
    TYPE_CHECKING,
    Optional,
    Union,
)
from ..utils import (
    transform_function_string,
    convert_dict_values_to_list,
    is_batchable,
    transform_json_log,
    RAY,
    RAY_AVAILABLE,
)
from ..utils import ExecutionContext
from ..processing.event_handler import EventHandler
from ..logs import LogWriter
from .. import prompts
import warnings
import traceback
import copy

if TYPE_CHECKING:
    from ..dataloading import Dataloader

StepOutput = Dict[str, List[Any]]
"""A dict mapping of output slot to Any list. Every Step outputs a StepOutput."""


LogType = Literal["info", "error", "json", "image"]
text_log_types = ["info", "error"]


def log(msg: Any, type: LogType = "info"):
    node_id: str = ExecutionContext.get("node_id")
    node_name: str = ExecutionContext.get("node_name")
    event_handler: EventHandler = ExecutionContext.get("event_handler")

    if node_id is None or node_name is None:
        raise ValueError("Can't find node info. Only initialized steps can log.")

    log_handle = None

    if event_handler:
        log_handle = event_handler.write_log
    elif RAY_AVAILABLE:
        if RAY.is_initialized():
            actor_handle = RAY.get_actor("_graphbook_RayStepHandler")
            log_handle = actor_handle.handle_log.remote
        else:
            raise ValueError(
                "View manager not initialized in context. Is this being called in a running graph?"
            )

    if type in text_log_types:
        log_message = msg
        if type == "error":
            log_message = f"[ERR] {msg}"
        print(f"[{node_id} {node_name}] {log_message}")

    elif type == "json":
        msg = transform_json_log(msg)
    elif type == "image":
        pass  # TODO
    else:
        raise ValueError(f"Unknown log type {type}")

    if log_handle:
        log_handle(node_id, msg, type)


def prompt(prompt: dict):
    node_id: str = ExecutionContext.get("node_id")
    event_handler: EventHandler = ExecutionContext.get("event_handler")
    if node_id is None:
        raise ValueError(
            f"Can't find node id in {caller}. Only initialized steps can log."
        )

    if event_handler is None:
        raise ValueError(
            "View manager not initialized in context. Is this being called in a running graph?"
        )

    event_handler.handle_prompt(node_id, prompt)


class Step:
    """
    The base class of the executable workflow node, step. All other step classes should be a descendant of this class.
    """

    RequiresInput = True
    Parameters = {}
    Outputs = ["out"]
    Category = ""

    def __init__(self, item_key=None):
        self.id = None
        self.item_key = item_key

    def set_context(self, **context):
        """
        Sets the context of the step. This is useful for setting the node_id and node_name of the step.

        Args:
            **context: The context to set
        """
        ExecutionContext.update(**context)

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

    def on_data(self, data: Any):
        """
        Executes upon receiving data

        Args:
            data (Any): The data input
        """
        pass

    def on_after_item(self, data: Any):
        """
        Executes after processing items

        Args:
            data (Any): The data input
        """
        pass

    def on_item(self, item: Any, data: Any):
        """
        Executes upon receiving an item. Is called after *on_data()* and before *on_after_item()*.

        Args:
            item (Any): The item to process
            data (Any): The data that the item belongs to
        """
        pass

    def on_clear(self):
        """
        Executes when a request to clear the step is made. This is useful for steps that have internal states that need to be reset.
        """
        pass

    def forward_note(self, data: Any) -> str:
        """
        Deprecated. Use :meth:`graphbook.core.steps.Step.route` instead.
        """
        warnings.warn(
            "forward_note is deprecated and will be removed in a future version of Graphbook. Use ``route`` instead.",
            DeprecationWarning,
        )
        return self.route(data)

    def route(self, data: Any) -> Union[str, StepOutput, None]:
        """
        Routes the item of data. Must return the corresponding output key or a dictionary of the form :data:`graphbook.core.steps.StepOutput`.
        Is called after *on_after_item()*.

        Args:
            data (Any): The data input

        Returns:
            A string that the data is associated with, or if multiple are being processed at a time, a StepOutput may be used.

        Example:
            The below examples assume that this step has two output pins, "dog" and "cat":

            .. highlight:: python
            .. code-block:: python

                def route(self, data: dict) -> str:
                    if data["is_dog"]:
                        return "dog"
                    return "cat"

            .. highlight:: python
            .. code-block:: python

                def route(self, data: dict) -> StepOutput:
                    dog_images = data["dog"]
                    cat_images = data["cat"]
                    return {
                        "dog": dog_images,
                        "cat": cat_images,
                    }
        """
        return "out"

    def __call__(self, data: Any) -> StepOutput:
        # 1. on_data -> 2. on_item -> 3. on_after_item -> 4. route
        self.on_data(data)

        if self.item_key is not None:
            get_method = getattr(data, "get", None)
            assert (
                get_method is not None
            ), f"Item key is only for dictionary-like data. {type(data)} is not a dictionary."

            item = data.get(self.item_key, None)
            assert item is not None, f"Item key {self.item_key} not found in data."
            self.on_item(item, data)

        self.on_after_item(data)

        out = self.route(data)
        output = {}
        if isinstance(out, str):
            output[out] = [data]
        elif isinstance(out, dict):
            output = out
        return output

    def all(self, data: List[Any]) -> StepOutput:
        out: StepOutput = {}
        if data is None:
            return out

        for d in data:
            step_output = self(d)
            for k, v in step_output.items():
                if k not in out:
                    out[k] = []
                out[k].extend(v)

        return out


class SourceStep(Step):
    """
    A Step that accepts no input but produce outputs.
    This this class will attempt to load all data at once, so it is recommended to use GeneratorSourceStep especially for large datasets.
    """

    def __init__(self):
        super().__init__()

    def load(self) -> StepOutput:
        """
        Function to load data. Must output a dictionary of outputs.

        Example:
            .. highlight:: python
            .. code-block:: python

                return {
                    "out": [{"images": [PIL.Image("image_of_dog.png")]}]
                }
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
        Function to load data. Must output a generator that yields dictionary of outputs.

        Example:
            .. highlight:: python
            .. code-block:: python

                yield {
                    "out": [{"images": [PIL.Image("image_of_dog.png")]}]
                }
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

    def in_q(self, data: Optional[Any]):
        if data is None:
            return
        self._in_queue.append(data)

    def is_active(self) -> bool:
        return len(self._in_queue) > 0

    def __call__(self) -> StepOutput:
        # 1. on_data -> 2. on_item -> 3. on_after_item -> 4. route
        if len(self._out_queue) == 0:
            return {}
        data = self._out_queue.pop(0)
        return super().__call__(data)

    def all(self) -> StepOutput:
        return self.__call__()


class AnyItemHolders:
    def __init__(self):
        self.item_counts = {}
        self.datas = {}
        self.completed = {}

    def handle_data(self, data: Any):
        obj_id = id(data)
        if obj_id not in self.datas:
            self.datas[obj_id] = data
        if obj_id not in self.item_counts:
            self.item_counts[obj_id] = 0
        self.item_counts[obj_id] += 1

    def handle_item(self, obj_id):
        self.item_counts[obj_id] -= 1

    def set_completed(self, data: Any):
        obj_id = id(data)
        self.completed[obj_id] = data
        if obj_id not in self.item_counts:
            self.item_counts[obj_id] = 0

    def pop_all_completed(self):
        completed = []
        to_remove = []
        for obj_id in self.completed:
            if self.item_counts[obj_id] == 0:
                completed.append(self.completed[obj_id])
                to_remove.append(obj_id)
                del self.item_counts[obj_id]
        for obj_id in to_remove:
            del self.completed[obj_id]
        return completed

    def is_active(self):
        return len(self.completed) > 0


StepData = Tuple[List[Any], List[Any], List[Any]]


class BatchStep(AsyncStep):
    """
    A Step used for batch and parallel processing using custom function definitions.
    Override the `load_fn` and `dump_fn` methods with your custom logic to load and dump data, respectively.
    """

    def __init__(self, batch_size, item_key):
        super().__init__(item_key=item_key)
        self.batch_size = int(batch_size)
        self.loaded_datas = {}
        self.num_loaded_datas = {}
        self.dumped_item_holders = AnyItemHolders()
        self.accumulated_items = [[], [], []]
        self.load_fn_params = {}
        self.dump_fn_params = {}
        self.parallelized_load = self.load_fn != BatchStep.load_fn

    def in_q(self, data: Optional[Any]):
        """
        Enqueue an item of data to be processed by the step

        Args:
            data (Any): The input
        """
        if data is None:
            return
        self.on_data(data)

        assert (
            getattr(data, "get", None) is not None
        ), f"BatchSteps can only accept dictionary-like data. {type(data)} is not a dictionary."
        items = data.get(self.item_key, None)
        if items is None:
            raise ValueError(f"Item key {self.item_key} not found in data.")

        if not is_batchable(items):
            items = [items]

        if len(items) > 0:
            # Load
            if self.parallelized_load:
                data_id = id(data)
                dataloader: Dataloader = ExecutionContext.get("dataloader")
                dataloader.put_load(items, self.load_fn_params, data_id, id(self))
                self.loaded_datas[data_id] = data
                self.num_loaded_datas[data_id] = len(items)
            else:
                acc_items, acc_datas, _ = self.accumulated_items
                for item in items:
                    acc_items.append(item)
                    acc_datas.append(data)

    def on_clear(self):
        self.loaded_datas = {}
        self.num_loaded_datas = {}
        self.dumped_item_holders = AnyItemHolders()
        self.accumulated_items = [[], [], []]

    def get_batch_sync(self, flush: bool = False) -> StepData:
        items, datas, _ = self.accumulated_items
        if len(items) == 0:
            return None
        if len(items) < self.batch_size:
            if not flush:
                return None

        b_items, b_datas, b_completed = [], [], []
        for _ in range(self.batch_size):
            item = items.pop(0)
            data = datas.pop(0)
            b_items.append(item)
            b_datas.append(data)
            if len(datas) == 0 or data is not datas[0]:
                b_completed.append(data)

        batch = (b_items, b_datas, b_completed)
        return batch

    def get_batch(self, flush: bool = False) -> StepData:
        if not self.parallelized_load:
            return self.get_batch_sync()

        items, datas, completed = self.accumulated_items
        dataloader: Dataloader = ExecutionContext.get("dataloader")
        next_in = dataloader.get_load(id(self))
        if next_in is not None:
            item, data_id = next_in
            # get original data (not pickled one)
            data = self.loaded_datas[data_id]
            if item is not None:
                items.append(item)
                datas.append(data)
            remaining_items = self.num_loaded_datas[data_id] - 1
            if remaining_items > 0:
                self.num_loaded_datas[data_id] = remaining_items
            else:
                del self.num_loaded_datas[data_id]
                del self.loaded_datas[data_id]
                completed.append(data)
        else:
            if len(self.accumulated_items[0]) == 0:
                return None

        if len(items) == 0:
            return None
        if len(items) < self.batch_size:
            if not flush:
                return None
            else:
                if len(self.loaded_datas) > 0:
                    return None

        batch = (items[: self.batch_size], datas[: self.batch_size], completed)
        self.accumulated_items = (
            items[self.batch_size :],
            datas[self.batch_size :],
            [],
        )
        return batch

    def dump_data(self, data: Any, output):
        """
        Dumps data to be processed by the worker pool. This is called after the step processes the batch of items.
        The class must have a dump_fn method that takes in the output data and returns a string path to the dumped data.

        Args:
            data (Any): The data input
            item_key (str): The item key to dump
            output (Any): The output data to dump
        """
        self.dumped_item_holders.handle_data(data)
        dataloader: Dataloader = ExecutionContext.get("dataloader")
        dataloader.put_dump(output, id(data), id(self))

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
        loaded, datas, completed = batch
        if self.parallelized_load:
            outputs = [l[0] for l in loaded]
            indexes = [l[1] for l in loaded]
            items = []
            for data, index in zip(datas, indexes):
                item = data.get(self.item_key)
                if is_batchable(item):
                    items.append(item[index])
                else:
                    items.append(item)
        else:
            outputs = None
            items = loaded

        data_dump = self.on_item_batch(outputs, items, datas)
        if data_dump is not None:
            if isinstance(data_dump, dict):
                # Dict returns are deprecated
                warnings.warn(
                    "dict returns for on_item_batch are deprecated and will be removed in a future version. Please return a list of your parameter tuples to provide to dump_fn instead.",
                    DeprecationWarning,
                )
                for k, v in data_dump.items():
                    if len(datas) != len(v):
                        self.log(
                            f"Unexpected number of datas ({len(datas)}) does not match returned outputs ({len(v)}). Will not write outputs!"
                        )
                    else:
                        for data, out in zip(datas, v):
                            self.dump_data(data, out)
            else:
                for data, out in zip(datas, data_dump):
                    self.dump_data(data, out)

        for data in completed:
            self.dumped_item_holders.set_completed(data)

    def handle_completed_data(self):
        dataloader: Dataloader = ExecutionContext.get("dataloader")
        data_id = dataloader.get_dump(id(self))
        if data_id is not None:
            self.dumped_item_holders.handle_item(data_id)
        output: StepOutput = {}
        for data in self.dumped_item_holders.pop_all_completed():
            self.on_after_item(data)
            output_key = self.route(data)
            if output_key not in output:
                output[output_key] = []
            output[output_key].append(data)
        return output

    def on_item_batch(self, outputs, items, data) -> Optional[List[Tuple[Any]]]:
        """
        Called when B items are loaded and are ready to be processed where B is *batch_size*. This is meant to be overriden by subclasses.

        Args:
            outputs (List[Any]): The list of loaded outputs of length B
            items (List[Any]): The list of anys of length B associated with outputs. This list has the same order as outputs does
                along the batch dimension
            data (List[Any]): The list of Anys of length B associated with outputs. This list has the same order as outputs does
                along the batch dimension

        Returns:
            Optional[List[Tuple[Any]]]: The output data to be dumped as a list of parameters to be passed to dump_fn. If None is returned, nothing will be dumped.
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

        output = self.handle_completed_data()
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
            len(self.loaded_datas) > 0
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
        self._awaiting_data = None

    def handle_prompt_response(self, response: Any):
        data = self._awaiting_data
        try:
            assert data is not None, "PromptStep is not awaiting a response."
            self.on_prompt_response(data, response)
            self._out_queue.append(data)
        except Exception as e:
            self.log(f"{type(e).__name__}: {str(e)}", "error")
            traceback.print_exc()

        self._is_awaiting_response = False
        self._awaiting_data = None
        prompt(prompts.none())

    def on_clear(self):
        """
        Clears any awaiting prompts and the prompt queue.
        If you plan on overriding this method, make sure to call super().on_clear() to ensure the prompt queue is cleared.
        """
        self._is_awaiting_response = False
        self._awaiting_data = None
        prompt(prompts.none())
        super().on_clear()

    def get_prompt(self, data: Any) -> dict:
        """
        Returns the prompt to be displayed to the user.
        This method can be overriden by the subclass.
        By default, it will return a boolean prompt.
        If None is returned, the prompt will be skipped on this data.
        A list of available prompts can be found in ``graphbook.prompts``.

        Args:
            data (Any): The Any input to display to the user
        """
        return prompts.bool_prompt(data)

    def on_prompt_response(self, data: Any, response: Any):
        """
        Called when the user responds to the prompt.
        This method must be overriden by the subclass.

        Args:
            data (Any): The Any input that was prompted
            response (Any): The user's response
        """
        raise NotImplementedError(
            "on_prompt_response must be implemented for PromptStep"
        )

    def __call__(self):
        if not self._is_awaiting_response and len(self._in_queue) > 0:
            data = self._in_queue.pop(0)
            p = self.get_prompt(data)
            if p:
                prompt(self.get_prompt(data))
                self._is_awaiting_response = True
                self._awaiting_data = data
            else:
                self._out_queue.append(data)
        return super().__call__()

    def is_active(self) -> bool:
        return len(self._in_queue) > 0 or self._awaiting_data is not None


class Split(Step):
    """
    Routes incoming Anys into either of two output slots, A or B. If split_fn
    evaluates to True, the data will be forwarded to A, else the data will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *forward_data(data)* where each data is fed into *split_fn(data)*.
    """

    RequiresInput = True
    Parameters = {"split_fn": {"type": "resource"}}
    Outputs = ["A", "B"]
    Category = "Filtering"

    def __init__(self, split_fn):
        super().__init__()
        self.split_fn = split_fn
        self.fn = transform_function_string(split_fn)

    def route(self, data) -> str:
        split_result = self.fn(data)
        if split_result:
            return "A"
        return "B"


class SplitByItems(Step):
    """
    Routes incoming Anys into either of two output slots, A or B. If split_fn evaluates to True,
    the data will be forwarded to A, else the data will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *route(data)* where each data and selected items is fed into \
        *split_fn(items, datas)*.
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

    def route(self, data: Any) -> StepOutput:
        split_result = self.fn(items=data.items[self.item_key], data=data)
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
        will be evaluated on *on_after_item(data)* where each selected item from item_key is fed into \
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

    def on_after_item(self, data: Any) -> StepOutput:
        a_items = []
        b_items = []
        for item in data.items[self.item_key]:
            if self.fn(item=item):
                a_items.append(item)
            else:
                b_items.append(item)
        data[self.a_key] = a_items
        data[self.b_key] = b_items
        if self.should_delete_original:
            del data[self.item_key]


class Copy(Step):
    """
    Copies the incoming datas to output slots A and B.
    The original version will be forwarded to A and an indentical copy will be forwarded to B.
    The copy is made with `copy.deepcopy()`.
    """

    RequiresInput = True
    Parameters = {}
    Category = "Util"
    Outputs = ["A", "B"]

    def __init__(self):
        super().__init__()

    def route(self, data: Any) -> StepOutput:
        return {"A": [data], "B": [copy.deepcopy(data)]}

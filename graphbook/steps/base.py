from __future__ import annotations
from typing import List, Dict, Tuple
import json
from graphbook.dataloading import Dataloader
from graphbook.custom_nodes import transform_function_string


class DataItem:
    """
    Data structure containing the text, audio, image, or video coupled with its annotation.

    Args:
        item (str): A path to media, string of text, or the actual data item to store
        type (str): Optional string to specify the type of data this is
        annotation (dict): A dictionary of annotations for this item

    Example:
        .. highlight:: python
        .. code-block:: python

            d = DataItem("path/to/image.jpg", "image", {"prediction": "dog"})
    """

    def __init__(self, item, type=None, annotation={}):
        self.item = item
        self.type = type
        self.annotation = annotation

    def __str__(self):
        return f"{'('+self.type+')' if self.type else ''}Item {self.item}: Annotations: {self.annotation}"

    def json(self):
        """
        Returns DataItem into a serialized JSON format
        """
        return {"item": self.item, "type": self.type, "annotation": self.annotation}


class DataRecord:
    """
    The unit that passes through workflow steps. DataRecords contains a dictionary of DataItems related to the record,
    and a dictionary of annotations.
    It also contains the property "key" which is useful to set with a unique id as in its id from its original database.

    Args:
        key (str): An optional key or id
        annotation (Dict[str, str]): An optional dictionary of annotations for this item
        items (Dict[str, List[DataItems]]): An optional dictionary of DataItems

    Example:
        .. highlight:: python
        .. code-block:: python

            d = DataRecord( "0123456789", {"prediction": "dog"}, {"images": [DataItem("image_of_dog.png")]} )
    """

    def __init__(self, key: str = "", annotation: dict = {}, items: dict = {}):
        self.key: str = key
        self.annotation: dict = annotation
        for k, v in items.items():
            if not isinstance(v, list):
                items[k] = [v]
            # Convert to list of DataItems
            for i, item in enumerate(v):
                if not isinstance(item, DataItem):
                    if isinstance(item, dict):
                        v[i] = DataItem(
                            item["item"], item.get("type"), item.get("annotation")
                        )
                    else:
                        v[i] = DataItem(item)
        self.items = items

    def put_item(self, item_key: str, item_value: str):
        """
        A convenient function to add a DataItem to an item list

        Args:
            item_key (str): The item key to append to
            item_value (str): The value of the item
        """
        if self.items.get(item_key) is None:
            self.items[item_key] = []
        self.items[item_key].append(DataItem(item_value))

    def json(self):
        """
        Returns DataRecord in a serialized JSON format
        """
        record_entry = {
            "key": self.key,
            "annotation": self.annotation,
            "items": {k: [item.json() for item in v] for k, v in self.items.items()},
        }
        return record_entry

    def __str__(self):
        return json.dumps(self.json())


StepOutput = Dict[str, List[DataRecord]]
"""A dict mapping of output slot to DataRecord list. Every Step outputs a StepOutput."""


class Step:
    """
    The base class of an executable workflow node. All other workflow nodes should inherit from Step.

    Args:
        key (str): An optional key or id
        annotation (Dict[str, str]): An optional dictionary of annotations for this item
        items (Dict[str, List[DataItems]]): An optional dictionary of DataItems
    """

    def __init__(self, id, logger, item_key=None):
        self.id = id
        self.logger = logger
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

    def on_before_items(self, data_record: DataRecord):
        """
        Executes upon receiving a DataRecord and before receiving the selected DataItems

        Args:
            data_record (DataRecord): The DataRecord input
        """
        pass

    def on_after_items(self, data_record: DataRecord):
        """
        Executes upon receiving a Datarecord and after processing the selected DataItems

        Args:
            data_record (DataRecord): The DataRecord input
        """
        pass

    def on_item(self, item: DataItem, data_record: DataRecord):
        """
        Executes upon receiving a DataItem. Is called after *on_before_items()*.

        Args:
            item (DataItem): The DataItem input
            data_record (DataRecord): The DataRecord that the DataItem belongs to
        """
        pass

    def forward_record(self, data_record: DataRecord) -> str | StepOutput:
        """
        Routes a DataRecord. Must return the corresponding output key or a dictionary that contains DataRecords.
        Is called after *on_after_items()*.

        Args:
            data_record (DataRecord): The DataRecord input

        Returns:
            A string that the record is associated with, or if multiple records are being processed at a time, a StepOutput may be used.
        """
        return "out"

    def __call__(self, data_record: DataRecord) -> StepOutput:
        # 1. on_before_items -> 2. on_item -> 3. on_after_items -> 4. forward_record
        self.on_before_items(data_record)

        if self.item_key is not None:
            items = data_record.items.get(self.item_key, None)
            assert (
                items is not None
            ), f"Item key {self.item_key} not found in data record. Cannot retrieve DataItem list."
            for item in items:
                self.on_item(item, data_record)

        self.on_after_items(data_record)

        out = self.forward_record(data_record)
        output = {}
        if isinstance(out, str):
            output[out] = [data_record]
        elif isinstance(out, dict):
            output = out
        return output

    def all(self, data_records: List[DataRecord]) -> StepOutput:
        step_outputs = []
        if data_records is not None:
            for record in data_records:
                step_output = self(record)
                if step_output is not None:
                    step_outputs.append(step_output)

        if len(step_outputs) == 0:
            return {}

        output_keys = step_outputs[0].keys()
        return {
            k: [
                record
                for step_output in step_outputs
                for record in step_output.get(k, [])
            ]
            for k in output_keys
        }

    def __str__(self):
        def get_str(step, indent):
            s = f"{' ' * indent}({step._id}) {type(step).__name__}\n"
            for child in step.children.values():
                for c in child:
                    s += get_str(c, indent + 2)
            return s

        return get_str(self, 0)


class SourceStep(Step):
    """
    A Step that accepts no input but produce outputs.
    """

    def __init__(self, id, logger):
        super().__init__(id, logger)

    def load(self) -> StepOutput:
        """
        Function to load data and convert into DataRecords. Must output a dictionary of DataRecords.
        """
        raise NotImplementedError("load function must be implemented for SourceStep")

    def __call__(self):
        result = self.load()
        for k, v in result.items():
            if not isinstance(v, list):
                result[k] = [v]
        return result


class AsyncStep(Step):
    """
    Asynchronous processing step that will consume everything in the in_queue so that the main thread can handle the outputs.
    Useful for parallel processing where the task can be optimized with multiple processes and the main thread can continue
    processing the rest of the graph.
    """

    def __init__(self, id, logger, item_key=None):
        super().__init__(id, logger, item_key)
        self._is_processing = True
        self._in_queue = []
        self.dl = None

    def set_dataloader(self, dataloader: Dataloader):
        self.dl = dataloader

    def in_q(self, data_record: DataRecord):
        if data_record is None:
            return
        self._in_queue.append(data_record)

    def is_active(self) -> bool:
        return self._is_processing


class RecordItemHolders:
    def __init__(self):
        self.item_counts = {}
        self.records = {}
        self.completed_records = {}

    def handle_record(self, record: DataRecord):
        record_id = id(record)
        if record_id not in self.records:
            self.records[record_id] = record
        if record_id not in self.item_counts:
            self.item_counts[record_id] = 0
        self.item_counts[record_id] += 1

    def handle_item(self, record_id, item_response):
        self.item_counts[record_id] -= 1
        if item_response is None:
            return
        item_key, output_fn = item_response
        self.records[record_id].put_item(item_key, output_fn)

    def set_completed(self, record: DataRecord):
        record_id = id(record)
        self.completed_records[record_id] = record
        if record_id not in self.item_counts:
            self.item_counts[record_id] = 0

    def pop_all_completed(self):
        completed = []
        to_remove = []
        for record_id in self.completed_records:
            if self.item_counts[record_id] == 0:
                completed.append(self.completed_records[record_id])
                to_remove.append(record_id)
                del self.item_counts[record_id]
        for record_id in to_remove:
            del self.completed_records[record_id]
        return completed

    def is_active(self):
        return len(self.completed_records) > 0


StepData = Tuple[List[DataItem], List[DataRecord], List[DataRecord]]


class BatchStep(AsyncStep):
    """
    A Step used for batch processing. This step will consume Pytorch tensor batches loaded by the worker pool by default.
    """

    def __init__(self, id, logger, batch_size, item_key):
        super().__init__(id, logger, item_key=item_key)
        self.batch_size = int(batch_size)
        self.loaded_data_records = {}
        self.num_loaded_data_records = {}
        self.dumped_item_holders = RecordItemHolders()
        self.accumulated_items = [[], [], []]

    def in_q(self, data_record: DataRecord):
        """
        Enqueue a data record to be processed by the step

        Args:
            data_record (DataRecord): The DataRecord input
        """
        if data_record is None:
            return
        self.on_before_items(data_record)
        items = data_record.items[self.item_key]

        # Load
        if hasattr(self, "load_fn"):
            if len(items) > 0:
                dr_id = id(data_record)
                self.dl.put_load(items, dr_id, self.load_fn, id(self))

                self.loaded_data_records[dr_id] = data_record
                self.num_loaded_data_records[dr_id] = len(items)

    def get_batch(self, flush: bool = False) -> StepData:
        items, records, completed = self.accumulated_items
        next_in = self.dl.get_load(id(self))
        if next_in is not None:
            item, record_id = next_in
            # get original record (not pickled one)
            record = self.loaded_data_records[record_id]
            if item is not None:
                items.append(item)
                records.append(record)
            remaining_items = self.num_loaded_data_records[record_id] - 1
            if remaining_items > 0:
                self.num_loaded_data_records[record_id] = remaining_items
            else:
                del self.num_loaded_data_records[record_id]
                del self.loaded_data_records[record_id]
                completed.append(record)
        else:
            if len(self.accumulated_items[0]) == 0:
                return None

        if len(items) == 0:
            return None
        if len(items) < self.batch_size:
            if not flush:
                return None
            else:
                if len(self.loaded_data_records) > 0:
                    return None

        batch = (items[: self.batch_size], records[: self.batch_size], completed)
        self.accumulated_items = (
            items[self.batch_size :],
            records[self.batch_size :],
            [],
        )
        return batch

    def dump_data(self, data_record: DataRecord, item_key, output):
        self.dumped_item_holders.handle_record(data_record)
        self.dl.put_dump(output, item_key, id(data_record), self.dump_fn, id(self))

    def handle_batch(self, batch: StepData):
        items, records, completed = batch
        tensors = [item[0] for item in items]
        indexes = [item[1] for item in items]
        items = [
            record.items[self.item_key][index]
            for record, index in zip(records, indexes)
        ]
        data_dump = self.on_item_batch(tensors, items, records)
        if data_dump is not None:
            for k, v in data_dump.items():
                if len(records) != len(v):
                    self.logger.log(
                        f"Unexpected number of records ({len(records)}) does not match returned outputs ({len(v)}). Will not write outputs!"
                    )
                else:
                    for record, out in zip(records, v):
                        self.dump_data(record, k, out)

        for record in completed:
            self.dumped_item_holders.set_completed(record)

    def handle_completed_records(self):
        data = self.dl.get_dump(id(self))
        if data is not None:
            record_id, item_response = data
            self.dumped_item_holders.handle_item(record_id, item_response)
        output = {}
        for record in self.dumped_item_holders.pop_all_completed():
            self.on_after_items(record)
            output_key = self.forward_record(record)
            if output_key not in output:
                output[output_key] = []
            output[output_key].append(record)
        return output

    def on_item_batch(self, tensor, items, records):
        """
        Called when B items are loaded into PyTorch tensors and are ready to be processed where B is *batch_size*. This is meant to be overriden by subclasses.


        Args:
            tensors (List[torch.Tensor]): The list of loaded tensors of length B
            items (List[DataItem]): The list of DataItems of length B associated with tensors. This list has the same order as tensors does
                along the batch dimension
            records (List[DataRecord]): The list of DataRecords of length B associated with tensors. This list has the same order as tensor does
                along the batch dimension
        """
        pass

    def __call__(self, flush: bool = False):
        """
        Batches input and executes the step if accumulated batch is equal to batch_size. Returns true if step is executed.
        """
        batch = self.get_batch(flush)
        if batch:
            self.handle_batch(batch)

        output = self.handle_completed_records()
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
            len(self.loaded_data_records) > 0
            or len(self.accumulated_items[0]) > 0
            or self.dumped_item_holders.is_active()
        )


class Split(Step):
    """
    Routes incoming DataRecords into either of two output slots, A or B. If split_fn
    evaluates to True, the record will be forwarded to A, else the record will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *forward_record(record)* where each record is fed into *split_fn(record)*.
    """

    RequiresInput = True
    Parameters = {"split_fn": {"type": "function"}}
    Outputs = ["A", "B"]
    Category = "Filtering"

    def __init__(self, id, logger, split_fn):
        super().__init__(id, logger)
        self.split_fn = split_fn
        self.fn = transform_function_string(split_fn)

    def forward_record(self, record) -> str:
        split_result = self.fn(data_record=record)
        if split_result:
            return "A"
        return "B"


class SplitRecordsByItems(Step):
    """
    Routes incoming DataRecords into either of two output slots, A or B. If split_fn evaluates to True,
    the record will be forwarded to A, else the record will be forwarded to B.

    Args:
        split_fn (str): A Python syntax function. The str must contain the function header (def ...). The function \
        will be evaluated on *forward_record(record)* where each record and selected items is fed into \
        *split_fn(items, records)*.
    """

    RequiresInput = True
    Parameters = {
        "split_items_fn": {"type": "function"},
        "item_key": {"type": "string"},
    }
    Outputs = ["A", "B"]
    Category = "Filtering"

    def __init__(self, id, logger, split_items_fn, item_key):
        super().__init__(id, logger, item_key=item_key)
        self.split_fn = split_items_fn
        self.fn = transform_function_string(split_items_fn)

    def forward_record(self, record: DataRecord) -> StepOutput:
        split_result = self.fn(items=record.items[self.item_key], record=record)
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
        will be evaluated on *on_after_items(record)* where each selected item from item_key is fed into \
        *split_fn(item)*.
        item_key (str): Original item_key that the items come from
        a_key (str): Will append item to DataItem list associated with the a_key if *split_fn(item)* evaluates to True
        b_key (str): Will append item to DataItem list associated with the b_key if *split_fn(item)* evaluates to False
        should_delete_original (str): If True, will delete original DataItem key-value pair of item_key. Defaults to True
        
    """

    RequiresInput = True
    Parameters = {"split_fn": {"type": "function"}, "item_key": {"type": "string"}}
    Category = "Filtering"
    Outputs = ["out"]

    def __init__(
        self, id, logger, split_fn, item_key, a_key, b_key, should_delete_original=True
    ):
        super().__init__(id, logger, item_key=item_key)
        self.split_fn = split_fn
        self.fn = transform_function_string(split_fn)
        self.a_key = a_key
        self.b_key = b_key
        self.should_delete_original = should_delete_original

    def on_after_items(self, record: DataRecord) -> StepOutput:
        a_items = []
        b_items = []
        for item in record.items[self.item_key]:
            if self.fn(item=item):
                a_items.append(item)
            else:
                b_items.append(item)
        record.items[self.a_key] = a_items
        record.items[self.b_key] = b_items
        if self.should_delete_original:
            del record.items[self.item_key]

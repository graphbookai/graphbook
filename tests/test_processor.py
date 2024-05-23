from graphbook.processor import Sequential, TreeProcessor, Print, Copy, LoadJSONL, Step, DataRecord, SplitRecordsByItems, StepOutput, StepData, BatchStep
from arithmetic import SumByConstant, DivByConstant, MulByConstant, NumDataRecord, NumListDataRecord
from typing import List
import os

class AssertStep(Step):
    def __init__(self, assertions: List):
        super().__init__(item_key="num")
        self.assertions = assertions
        self.current_assertion = 0

    def exec(self, data: StepData) -> StepOutput:
        items, _, completed = data
        assert self.assertions[self.current_assertion](items)
        self.current_assertion = (self.current_assertion + 1) % len(self.assertions)
        return {
            "next": completed
        }

def test_single_step():
    steps = AssertStep([lambda items: items[0].item == 1])
    TreeProcessor(steps).run( [NumDataRecord("num", 1)] )

def test_split():
    a_step = Sequential([
        MulByConstant(10),
        AssertStep([lambda items: items[0].item == 10])
    ])
    b_step = Sequential([
        DivByConstant(10),
        AssertStep([lambda items: items[0].item == 1])
    ])
    steps = SplitRecordsByItems(
        lambda items: items[0].item < 5,
        item_key="num",
        a_step=a_step,
        b_step=b_step
    )
   
    TreeProcessor(steps).run( [NumDataRecord("num", 1), NumDataRecord("num", 10)] )

def test_sequential():
    steps = Sequential([
        SumByConstant(5),
        DivByConstant(2),
        AssertStep([lambda items: items[0].item == 4]),
    ])

    TreeProcessor(steps).run( [NumDataRecord("num", 3)] )

def test_copy():
    steps = Copy([
        Sequential([
            SumByConstant(6),
            AssertStep([lambda items: items[0].item == 8])
        ]),
        Sequential([
            DivByConstant(2),
            AssertStep([lambda items: items[0].item == 1])
        ])
    ])

    TreeProcessor(steps).run( [NumDataRecord("num", 2)] )

def test_batchsteps_are_flushed():
    data_records = [NumDataRecord("num", 1), NumDataRecord("num", 2), NumDataRecord("num", 3)]
    steps = Sequential([
        Print(),
        SumByConstant(2, batch_size=2),
    ])

    TreeProcessor(steps).run( data_records )
    assert data_records[0].items["num"][0].item == 3
    assert data_records[1].items["num"][0].item == 4
    assert data_records[2].items["num"][0].item == 5

def test_batchstep_returns_only_complete_records():
    steps = Sequential([
        SumByConstant(2, batch_size=2),
        AssertStep([
            lambda items: items[0].item == 3,
            lambda items: items[0].item == 4,
            lambda items: items[1].item == 5
        ]),    
    ])

    TreeProcessor(steps).run( [NumDataRecord("num", 1), NumListDataRecord("nums", [2, 3])] )

def test_example_tree():
    steps = Sequential([
        SumByConstant(5),
        Copy([
            Sequential([
                MulByConstant(2),
                DivByConstant(4),
                AssertStep([lambda items: items[0].item == 5, lambda items: items[0].item == 6]),
            ]),
            Sequential([
                MulByConstant(4, batch_size=2),
                AssertStep([lambda items: items[0].item == 40, lambda items: items[0].item == 48]),
            ])
        ])
    ])

    TreeProcessor(steps).run( LoadJSONL("test_inputs/example_tree_inputs.jsonl") )

def test_multiprocessing():
    class MultiprocessingStep(BatchStep):
        def __init__(self):
            super().__init__(item_key="num", batch_size=2)
            MultiprocessingStep.curr_os_pid = os.getpid() # Should be main process pid

        @staticmethod
        def load_fn(item) -> any:
            # This should be called in a separate process each time
            assert MultiprocessingStep.curr_os_pid != os.getpid()
            MultiprocessingStep.curr_os_pid = os.getpid()
            print("Loading item", item)
            return item
        
        @staticmethod
        def dump_fn(items) -> None:
            # This should be called in a separate process each time
            assert MultiprocessingStep.curr_os_pid != os.getpid()
            MultiprocessingStep.curr_os_pid = os.getpid()
            print("Dumping batch", items)
            assert len(items) == 2, "Items should be batched"

        def exec(self, data: StepData) -> StepOutput:
            items, records, completed = data
            assert len(items) == 2, "Items should be batched"
            assert len(records) == 2, "Records should be batched"
            assert len(completed) == 2, "Completed records not in batch" 
            self.start_dump(items, self.dump_fn)
            return {
                "_next": completed
            }
    TreeProcessor(MultiprocessingStep(), num_workers=2).run( [NumDataRecord("num", 1), NumDataRecord("num", 2)] )

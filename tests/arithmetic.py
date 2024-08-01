from graphbook.steps.base import StepData, StepOutput, Note, any, BatchStep
from typing import List


class NumNote(Note):
    def __init__(self, num: int):
        super().__init__({"num": [num]})


class NumListNote(Note):
    def __init__(self, nums: List[int]):
        super().__init__({"num": nums})

class NumStep(BatchStep):
    def __init__(self, batch_size=-1):
        super().__init__(batch_size=batch_size, item_key="num")

    def exec(self, data: StepData) -> StepOutput:
        items, _, completed = data
        # Manipulate
        self.on_number(items)
        # Filter
        return {"_next": completed}


class SumByConstant(NumStep):
    def __init__(self, constant, batch_size=-1):
        super().__init__(batch_size=batch_size)
        self.constant = constant

    def on_number(self, numbers: List[any]):
        # Manipulate
        for num in numbers:
            num.item += self.constant


class DivByConstant(NumStep):
    def __init__(self, constant, batch_size=-1):
        super().__init__(batch_size=batch_size)
        self.constant = constant

    def on_number(self, numbers: List[any]):
        # Manipulate
        for num in numbers:
            num.item /= self.constant


class MulByConstant(NumStep):
    def __init__(self, constant, batch_size=-1):
        super().__init__(batch_size=batch_size)
        self.constant = constant

    def on_number(self, numbers: List[any]):
        # Manipulate
        for num in numbers:
            num.item *= self.constant

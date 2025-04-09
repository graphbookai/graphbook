import random
import graphbook as gb
from graphbook.core.steps import Step, GeneratorSourceStep


class GenerateNumbers(GeneratorSourceStep):
    Parameters = {"amount": {"type": "number", "default": 1000}}

    def __init__(self, amount=1000):
        super().__init__()
        self.amount = amount

    def load(self):
        for _ in range(self.amount):
            yield {"out": {"numbers": [random.randint(0, 10) for _ in range(4)]}}


class CalcMean(Step):
    def __init__(self):
        super().__init__()

    def on_data(self, data: dict):
        numbers = data["numbers"]
        mean = sum(numbers) / len(numbers)
        data["mean"] = mean


class Transform(Step):
    Parameters = {
        "scale": {"type": "number", "default": 1},
        "shift": {"type": "number", "default": 0},
    }

    def __init__(self, scale=1, shift=0):
        super().__init__()
        self.scale = scale
        self.shift = shift

    def on_data(self, data: dict):
        data["numbers"] = [num * self.scale + self.shift for num in data["numbers"]]


class CalcRunningMean(Step):
    def __init__(self):
        super().__init__()
        self.running_mean = 0
        self.count = 0

    def on_data(self, data: dict):
        mean = sum(data["numbers"]) / len(data["numbers"])
        self.running_mean = (self.running_mean * self.count + mean) / (self.count + 1)
        self.count += 1

    def on_end(self):
        self.log(self.running_mean)


g = gb.Graph()


@g()
def _():
    numbers = g.step(GenerateNumbers)
    mean = g.step(CalcMean)
    transformed = g.step(Transform)
    running_mean = g.step(CalcRunningMean)

    transformed.bind(numbers)
    mean.bind(transformed)
    running_mean.bind(transformed)


if __name__ == "__main__":
    g.run()

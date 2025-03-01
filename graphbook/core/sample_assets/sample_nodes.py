import random
from graphbook import step, source, param, event


@step("GenerateNumbers")
@source()
@param("amount", type="number", default=1000)
def generate_numbers(ctx):
    """
    Generates Python dicts containing a list of random numbers

    Args:
        num (int): Amount to generate
    """
    amount = ctx.amount
    for _ in range(amount):
        yield {"out": {"numbers": [random.randint(0, 10) for _ in range(4)]}}


@step("CalcMean")
def calc_mean(ctx, data):
    """
    Calculates the mean of the list.
    Will add a new key **"mean"** to the dict.
    """
    numbers = data["numbers"]
    mean = sum(numbers) / len(numbers)
    data["mean"] = mean


@step("Transform")
@param("scale", type="number", default=1)
@param("shift", type="number", default=0)
def transform(ctx, data):
    """
    Applies a linear transformation to the list of numbers.
    Will replace the list of numbers with the new list that is transformed.

    Args:
        scale (float): Scale factor
        shift (float): Shift factor
    """
    scale = ctx.scale
    shift = ctx.shift
    data["numbers"] = [num * scale + shift for num in data["numbers"]]


def calc_running_mean_init(ctx):
    ctx.running_mean = 0
    ctx.count = 0


def report_running_mean(ctx):
    ctx.log(ctx.running_mean)


@step("CalcRunningMean")
@event("__init__", calc_running_mean_init)
@event("on_end", report_running_mean)
def calc_running_mean(ctx, data):
    """
    A stateful step that calculates the running mean.
    Will log the running mean at the end of the workflow execution.
    """
    mean = data["mean"]
    ctx.running_mean = (ctx.running_mean * ctx.count + mean) / (ctx.count + 1)
    ctx.count += 1

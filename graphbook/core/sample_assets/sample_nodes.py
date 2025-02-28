import torch
from graphbook import step, source, param, event


@step("GenerateTensors")
@source()
@param("amount", type="number", default=1000)
def generate_tensors(ctx):
    """
    Generates Python dicts containing tensors and labels.

    Args:
        num (int): Amount to generate
    """
    amount = ctx.amount
    for _ in range(amount):
        yield {"tensor": torch.randn(10, 10), "label": torch.randint(0, 10, (1,)).item()}


@step("CalcMean")
def calc_mean(ctx, data):
    """
    Calculates the mean of the tensor.
    Will add a new key **"mean"** to the dict.
    """
    tensor = data["tensor"]
    mean = tensor.mean().item()
    data["mean"] = mean


@step("Transform")
@param("scale", type="number", default=1)
@param("shift", type="number", default=0)
def transform(ctx, data):
    """
    Applies a linear transformation to the tensor.
    Will replace the tensor with the transformed tensor.

    Args:
        scale (float): Scale factor
        shift (float): Shift factor
    """
    scale = ctx.scale
    shift = ctx.shift
    data["tensor"] = data["tensor"] * scale + shift


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
    A stateful step that calculates the running mean of the tensors in the Datas.
    Will log the running mean at the end of the workflow execution.
    """
    tensor = data["tensor"]
    mean = tensor.mean().item()
    ctx.running_mean = (ctx.running_mean * ctx.count + mean) / (ctx.count + 1)
    ctx.count += 1

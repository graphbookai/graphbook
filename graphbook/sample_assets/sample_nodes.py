import torch
from graphbook import Note, step, source, param, event


@step("GenerateTensors")
@source()
@param("num_notes", type="number", default=1000)
def generate_tensors(ctx):
    """
    Generates some fake data in the Notes containing tensors and labels.

    Args:
        num_notes (int): Number of Notes to generate
    """
    num_notes = ctx.num_notes
    for _ in range(num_notes):
        yield Note(
            {"tensor": torch.randn(10, 10), "label": torch.randint(0, 10, (1,)).item()}
        )


@step("CalcMean")
def calc_mean(ctx, note):
    """
    Calculates the mean of the tensor in the Note.
    Will add a new key **"mean"** to the Note.
    """
    tensor = note["tensor"]
    mean = tensor.mean().item()
    note["mean"] = mean


@step("Transform")
@param("scale", type="number", default=1)
@param("shift", type="number", default=0)
def transform(ctx, note):
    """
    Applies a linear transformation to the tensor in the Note.
    Will replace the tensor with the transformed tensor.

    Args:
        scale (float): Scale factor
        shift (float): Shift factor
    """
    scale = ctx.scale
    shift = ctx.shift
    note["tensor"] = note["tensor"] * scale + shift


def calc_running_mean_init(ctx):
    ctx.running_mean = 0
    ctx.count = 0


def report_running_mean(ctx):
    ctx.log(ctx.running_mean)


@step("CalcRunningMean")
@event("__init__", calc_running_mean_init)
@event("on_end", report_running_mean)
def calc_running_mean(ctx, note):
    """
    A stateful step that calculates the running mean of the tensors in the Notes.
    Will log the running mean at the end of the workflow execution.
    """
    tensor = note["tensor"]
    mean = tensor.mean().item()
    ctx.running_mean = (ctx.running_mean * ctx.count + mean) / (ctx.count + 1)
    ctx.count += 1

from graphbook.steps import Step
from graphbook import Note, step, event, output, param
import random


def forward(ctx: Step, note: Note) -> str:
    if random.random() < ctx.prob:
        return "A"
    return "B"


@step("Custom/MyFirstStep")
@param("prob", "number", default=0.5)
@event("forward_note", forward)
@output("A", "B")
def my_first_step(ctx: Step, note: Note):
    """
    This is a custom step that randomly forwards the input to either A or B given the probability `prob`.

    Args:
        prob (float): The probability of forwarding the input to A.
    """
    ctx.log(note["message"])

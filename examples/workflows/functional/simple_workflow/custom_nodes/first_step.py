from graphbook.steps import Step
from graphbook import step, event, output, param
import random


def route(ctx: Step, data: dict) -> str:
    if random.random() < ctx.prob:
        return "A"
    return "B"


@step("Custom/MyFirstStep")
@param("prob", "number", default=0.5)
@event("route", route)
@output("A", "B")
def my_first_step(ctx: Step, data: dict):
    """
    This is a custom step that randomly forwards the input to either A or B given the probability `prob`.

    Args:
        prob (float): The probability of forwarding the input to A.
    """
    ctx.log(data["message"])

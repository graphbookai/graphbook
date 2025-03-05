from graphbook import step, source, param
from graphbook.core.steps import Step


@step("Custom/MyFirstSource")
@source()
@param("amount", "number", default=10)
@param("message", "string", default="Hello, World!")
def my_first_source(ctx: Step):
    """
    This is a custom source step that creates 10 Python dicts with the same message.

    Args:
        message (str): The message to be used in the dict
    """
    for i in range(ctx.amount):
        yield {"out": {"message": f"{ctx.message} {i}/{ctx.amount}"}}

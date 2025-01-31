from graphbook import Note, step, source, param
from graphbook.steps import Step


@step("Custom/MyFirstSource")
@source()
@param("num_notes", "number", default=10)
@param("message", "string", default="Hello, World!")
def my_first_source(ctx: Step):
    """
    This is a custom source step that creates 10 notes with the same message.

    Args:
        message (str): The message to be used in the notes
    """
    for i in range(ctx.num_notes):
        yield Note({"message": f"{ctx.message} {i}/{ctx.num_notes}"})

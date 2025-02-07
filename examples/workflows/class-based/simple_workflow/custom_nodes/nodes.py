from graphbook.steps import Step
from graphbook import Note
import random


class MyFirstStep(Step):
    """
    This is a custom step that randomly forwards the input to either A or B given the probability `prob`.
    
    Args:
        prob (float): The probability of forwarding the input to A.
    """
    RequiresInput = True
    Parameters = {"prob": {"type": "resource"}}
    Outputs = ["A", "B"]
    Category = "Custom"

    def __init__(self, prob):
        super().__init__()
        self.prob = prob

    def on_after_items(self, note: Note) -> Note:
        self.log(note["message"])

    def forward_note(self, note: Note) -> str:
        if random.random() < self.prob:
            return "A"
        return "B"


from graphbook.steps import SourceStep


class MyFirstSource(SourceStep):
    """
    This is a custom source step that creates 10 notes with the same message.
    
    Args:
        message (str): The message to be used in the notes
    """
    RequiresInput = False
    Parameters = {"message": {"type": "string", "default": "Hello, World!"}}
    Outputs = ["message"]
    Category = "Custom"

    def __init__(self, message):
        super().__init__()
        self.message = message

    def load(self):
        return {"message": [Note({"message": self.message}) for _ in range(10)]}

    def forward_note(self, note: Note) -> str:
        return "message"

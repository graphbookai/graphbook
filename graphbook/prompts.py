from typing import Any, List
from .note import Note
from .utils import transform_json_log


def none():
    return {"type": None}


def prompt(note: Note, *, msg: str = "", show_images: bool = False, default: Any = ""):
    return {
        "note": transform_json_log(note),
        "msg": msg,
        "show_images": show_images,
        "def": default,
    }


def bool_prompt(
    note: Note,
    *,
    msg: str = "Continue?",
    style: str = "yes/no",
    default: bool = False,
    show_images: bool = False,
):
    """
    Prompt the user with a yes/no for binary questions.
    
    Args:
        note (Note): The current note that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        style (str): The style of the bool prompt. Can be "yes/no" or "switch".
        default (bool): The default bool value.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
    """
    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = "bool"
    p["options"] = {"style": style}
    return p

def selection_prompt(
    note: Note,
    choices: List[str],
    *,
    msg: str = "Select an option:",
    default: List[str] | str = None,
    show_images: bool = False,
    multiple_allowed: bool = False
):
    """
    Prompt the user to select an option from a list of choices.
    
    Args:
        note (Note): The current note that triggered the prompt.
        choices (List[str]): A list of strings representing the options the user can select.
        msg (str): An informative message or inquiry to display to the user.
        default (List[str] | str): The default value. If multiple_allowed is True, this should be a list of strings.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
        multiple_allowed (bool): Whether the user can select multiple options from the list of given choices.
    """
    assert len(choices) > 0, "Choices must not be empty in selection prompt."
    if default is None:
        if multiple_allowed:
            default = [choices[0]]
        else:
            default = choices[0]

    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = "selection"
    p["options"] = {
        "choices": choices,
        "multiple_allowed": multiple_allowed,
    }
    return p

def text_prompt(
    note: Note,
    *,
    msg: str = "Enter text:",
    default: str = "",
    show_images: bool = False,
):
    """
    Prompt the user to enter text.
    
    Args:
        note (Note): The current note that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (str): The default text value.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
    """
    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = "string"
    return p

def number_prompt(
    note: Note,
    *,
    msg: str = "Enter a number:",
    default: float = 0.0,
    show_images: bool = False,
):
    """
    Prompt the user to enter a number.
    
    Args:
        note (Note): The current note that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (float): The default number value.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
    """
    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = "number"
    return p

def dict_prompt(
    note: Note,
    *,
    msg: str = "Enter a dictionary:",
    default: dict = {},
    show_images: bool = False,
):
    """
    Prompt the user to enter a dictionary.
    
    Args:
        note (Note): The current note that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (dict): The default dictionary value.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
    """
    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = "dict"
    return p

def list_prompt(
    note: Note,
    type: str = "string",
    *,
    msg: str = "Enter a list:",
    default: list = [],
    show_images: bool = False,
):
    """
    Prompt the user to enter a list.
    
    Args:
        note (Note): The current note that triggered the prompt.
        type (str): The type of the list elements. Can be "string", "number", "dict", or "bool".
        msg (str): An informative message or inquiry to display to the user.
        default (list): The default list value.
        show_images (bool): Whether to present the images (instead of the Note object) to the user.
    """
    assert type in ["string", "number", "dict", "bool"], "Invalid type in list prompt."
    p = prompt(note, msg=msg, default=default, show_images=show_images)
    p["type"] = f"list[{type}]"
    return p

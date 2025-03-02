from typing import Any, List, Union
from .utils import transform_json_log

__all__ = [
    "bool_prompt",
    "selection_prompt",
    "text_prompt",
    "number_prompt",
    "dict_prompt",
    "list_prompt",
]


def none():
    return {"type": None}


def prompt(data: Any, *, msg: str = "", show_images: bool = False, default: Any = ""):
    return {
        "data": transform_json_log(data),
        "msg": msg,
        "show_images": show_images,
        "def": default,
    }


def bool_prompt(
    data: Any,
    *,
    msg: str = "Continue?",
    style: str = "yes/no",
    default: bool = False,
    show_images: bool = False,
):
    """
    Prompt the user with a yes/no for binary questions.
    
    Args:
        data (Any): The current data that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        style (str): The style of the bool prompt. Can be "yes/no" or "switch".
        default (bool): The default bool value.
        show_images (bool): Whether to present the images (instead of the raw data) to the user.
    """
    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = "bool"
    p["options"] = {"style": style}
    return p

def selection_prompt(
    data: Any,
    choices: List[str],
    *,
    msg: str = "Select an option:",
    default: Union[List[str], str, None] = None,
    show_images: bool = False,
    multiple_allowed: bool = False
):
    """
    Prompt the user to select an option from a list of choices.
    
    Args:
        data (Any): The current data that triggered the prompt.
        choices (List[str]): A list of strings representing the options the user can select.
        msg (str): An informative message or inquiry to display to the user.
        default (Union[List[str], str, None]): The default value. If multiple_allowed is True, this should be a list of strings.
        show_images (bool): Whether to present the images (instead of raw data) to the user.
        multiple_allowed (bool): Whether the user can select multiple options from the list of given choices.
    """
    assert len(choices) > 0, "Choices must not be empty in selection prompt."
    if default is None:
        if multiple_allowed:
            default = [choices[0]]
        else:
            default = choices[0]

    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = "selection"
    p["options"] = {
        "choices": choices,
        "multiple_allowed": multiple_allowed,
    }
    return p

def text_prompt(
    data: Any,
    *,
    msg: str = "Enter text:",
    default: str = "",
    show_images: bool = False,
):
    """
    Prompt the user to enter text.
    
    Args:
        data (Any): The current data that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (str): The default text value.
        show_images (bool): Whether to present the images (instead of the raw data) to the user.
    """
    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = "string"
    return p

def number_prompt(
    data: Any,
    *,
    msg: str = "Enter a number:",
    default: float = 0.0,
    show_images: bool = False,
):
    """
    Prompt the user to enter a number.
    
    Args:
        data (Any): The current data that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (float): The default number value.
        show_images (bool): Whether to present the images (instead of the raw data) to the user.
    """
    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = "number"
    return p

def dict_prompt(
    data: Any,
    *,
    msg: str = "Enter a dictionary:",
    default: dict = {},
    show_images: bool = False,
):
    """
    Prompt the user to enter a dictionary.
    
    Args:
        data (Any): The current data that triggered the prompt.
        msg (str): An informative message or inquiry to display to the user.
        default (dict): The default dictionary value.
        show_images (bool): Whether to present the images (instead of the raw data) to the user.
    """
    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = "dict"
    return p

def list_prompt(
    data: Any,
    type: str = "string",
    *,
    msg: str = "Enter a list:",
    default: list = [],
    show_images: bool = False,
):
    """
    Prompt the user to enter a list.
    
    Args:
        data (Any): The current data that triggered the prompt.
        type (str): The type of the list elements. Can be "string", "number", "dict", or "bool".
        msg (str): An informative message or inquiry to display to the user.
        default (list): The default list value.
        show_images (bool): Whether to present the images (instead of the raw data) to the user.
    """
    assert type in ["string", "number", "dict", "bool"], "Invalid type in list prompt."
    p = prompt(data, msg=msg, default=default, show_images=show_images)
    p["type"] = f"list[{type}]"
    return p

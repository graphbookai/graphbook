from typing import Any
from .note import Note
from .utils import transform_json_log

def prompt(note: Note, msg: str, show_images: bool=False, default: Any=""):
    return {
        "note": transform_json_log(note),
        "msg": msg,
        "show_images": show_images,
        "def": default
    }

def bool_prompt(note: Note, msg: str="", style: str="yes/no", default: bool=False, show_images: bool=False):
    p = prompt(note, msg, default=default, show_images=show_images)
    p["type"] = "bool"
    p["options"] = {
        "style": style
    }
    return p

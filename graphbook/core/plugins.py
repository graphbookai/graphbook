import importlib
import inspect
from .steps import Step
from .resources import Resource
from . import config

exported_steps = {}
exported_resources = {}
exported_web = {}


def setup_plugins():
    plugin_modules = config.get("plugins", [])
    for module in plugin_modules:
        importlib.import_module(module)

    steps = exported_steps
    resources = exported_resources
    web = exported_web
    return steps, resources, web


def export(name, cls):
    module_name = _get_caller_module()
    if issubclass(cls, Step):
        exported_steps.setdefault(module_name, {})[name] = cls
    elif issubclass(cls, Resource):
        exported_resources.setdefault(module_name, {})[name] = cls
    else:
        raise ValueError("Only Step and Resource classes can be exported")


def web(location):
    module_name = _get_caller_module()
    exported_web[module_name] = location


def _get_caller_module():
    caller_frame = inspect.stack()[2]
    return inspect.getmodule(caller_frame[0]).__name__

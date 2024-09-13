import graphbook.steps as steps
from typing import List, Dict


class StepClassFactory:
    def __init__(self, name, category, BaseClass=steps.Step):
        self.name = name
        self.category = category
        self.BaseClass = BaseClass
        self.events = {}
        self.Parameters = {}
        self.parameter_type_casts = {}
        self.RequiresInput = True
        self.Outputs = ["out"]
        self.is_outputs_specified = False

    def event(self, event, func):
        self.events[event] = func

    def param(
        self, name, type, cast_as=None, default=None, required=False, description=""
    ):
        if name not in self.Parameters:
            self.Parameters[name] = {
                "type": type,
                "default": default,
                "required": required,
                "description": description,
            }
            self.parameter_type_casts[name] = cast_as

    def source(self, is_generator=True):
        self.RequiresInput = False
        self.BaseClass = steps.GeneratorSourceStep if is_generator else steps.SourceStep

    def output(self, outputs):
        if not self.is_outputs_specified:
            self.is_outputs_specified = True
            self.Outputs = []
        self.Outputs.extend(outputs)

    def build(self):
        def __init__(cls, **kwargs):
            self.BaseClass.__init__(cls)  # might be only needed for Python 2
            for key, value in kwargs.items():
                if key in self.Parameters:
                    cast_as = self.parameter_type_casts[key]
                    if cast_as is not None:
                        value = cast_as(value)
                setattr(cls, key, value)

        cls_methods = {"__init__": __init__}
        for event, fn in self.events.items():
            cls_methods[event] = fn
        newclass = type(self.name, (self.BaseClass,), cls_methods)
        newclass.Category = self.category
        newclass.Parameters = self.Parameters
        newclass.RequiresInput = self.RequiresInput
        newclass.Outputs = self.Outputs
        return newclass


class DecoratorFunction:
    def __init__(self, next, fn, **kwargs):
        self.next = next
        self.fn = fn
        self.kwargs = kwargs


step_factories: Dict[str, StepClassFactory] = {}
resource_factories = {}


def get_steps():
    global step_factories
    steps = {}
    for name, factory in step_factories.items():
        steps[name] = factory.build()

    step_factories.clear()
    return steps


def step(name, event: str | None = None):
    def decorator(func):
        global step_factories
        short_name = name.split("/")[-1]
        category = "/".join(name.split("/")[:-1])
        factory = StepClassFactory(short_name, category)

        while isinstance(func, DecoratorFunction):
            func.fn(factory, **func.kwargs)
            func = func.next

        if event is not None:
            factory.event(event, func)
        else:
            if factory.BaseClass == steps.Step:
                factory.event("on_note", func)
            else:
                factory.event("load", func)

        step_factories[short_name] = factory

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def param(
    name: str,
    type: str,
    *,
    default=None,
    required: bool = False,
    description: str = "",
    cast_as: type | None = None,
):
    def decorator(func):
        def set_p(factory: StepClassFactory):
            factory.param(name, type, cast_as, default, required, description)

        return DecoratorFunction(func, set_p)

    return decorator


def source(is_generator=True):
    def decorator(func):
        def set_source(factory: StepClassFactory):
            factory.source(is_generator)

        return DecoratorFunction(func, set_source)

    return decorator


def sink():
    def decorator(func):
        def set_sink(factory: StepClassFactory):
            factory.sink()

        return DecoratorFunction(func, set_sink)

    return decorator


def output(*outputs: List[str]):
    def decorator(func):
        def set_output(factory: StepClassFactory):
            factory.output(outputs)

        return DecoratorFunction(func, set_output)

    return decorator

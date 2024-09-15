import graphbook.steps as steps
import graphbook.resources as resources
from typing import List, Dict
import abc


class NodeClassFactory:
    def __init__(self, name, category, BaseClass):
        self.name = name
        self.category = category
        self.BaseClass = BaseClass
        self.Parameters = {}
        self.parameter_type_casts = {}
        self.events = {}
        
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
        
    @abc.abstractmethod    
    def build():
        return None


class StepClassFactory(NodeClassFactory):
    def __init__(self, name, category, BaseClass=steps.Step):
        super().__init__(name, category, BaseClass)
        self.RequiresInput = True
        self.Outputs = ["out"]
        self.is_outputs_specified = False

    def source(self, is_generator=True):
        self.RequiresInput = False
        self.BaseClass = steps.GeneratorSourceStep if is_generator else steps.SourceStep

    def output(self, outputs):
        if not self.is_outputs_specified:
            self.is_outputs_specified = True
            self.Outputs = []
        self.Outputs.extend(outputs)

    def batch(
        self, default_batch_size: int | None, default_item_key: str | None, load_fn=None
    ):
        self.BaseClass = steps.BatchStep
        self.param(
            "batch_size",
            "number",
            default=default_batch_size,
            required=True,
            description="The size of the batch to be loaded",
        )
        self.param(
            "item_key",
            "string",
            default=default_item_key,
            required=True,
            description="The key to use for batching",
        )
        if load_fn is not None:
            self.event("load_fn", load_fn)

    def build(self):
        def __init__(cls, **kwargs):
            if self.BaseClass == steps.BatchStep:
                self.BaseClass.__init__(
                    cls, batch_size=kwargs["batch_size"], item_key=kwargs["item_key"]
                )
            else:
                self.BaseClass.__init__(cls)
            for key, value in kwargs.items():
                if key in self.Parameters:
                    cast_as = self.parameter_type_casts[key]
                    if cast_as is not None:
                        value = cast_as(value)
                setattr(cls, key, value)
            init_event = self.events.get("__init__")
            if init_event:
                init_event(cls, **kwargs)

        cls_methods = {"__init__": __init__}
        for event, fn in self.events.items():
            if event == "__init__":
                continue
            cls_methods[event] = fn
        newclass = type(self.name, (self.BaseClass,), cls_methods)
        newclass.Category = self.category
        newclass.Parameters = self.Parameters
        newclass.RequiresInput = self.RequiresInput
        newclass.Outputs = self.Outputs
        return newclass


class ResourceClassFactory(NodeClassFactory):
    def __init__(self, name, category, BaseClass=resources.Resource):
        super().__init__(name, category, BaseClass)

    def build(self):
        def __init__(cls, **kwargs):
            self.BaseClass.__init__(cls)
            for key, value in kwargs.items():
                if key in self.Parameters:
                    cast_as = self.parameter_type_casts[key]
                    if cast_as is not None:
                        value = cast_as(value)
                setattr(cls, key, value)

        cls_methods = {"__init__": __init__}
        for event, fn in self.events.items():
            if event == "__init__":
                continue
            cls_methods[event] = fn
        newclass = type(self.name, (self.BaseClass,), cls_methods)
        newclass.Category = self.category
        newclass.Parameters = self.Parameters
        return newclass


class DecoratorFunction:
    def __init__(self, next, fn, **kwargs):
        self.next = next
        self.fn = fn
        self.kwargs = kwargs


step_factories: Dict[str, StepClassFactory] = {}
resource_factories: Dict[str, ResourceClassFactory] = {}


def get_steps():
    global step_factories
    steps = {}
    for name, factory in step_factories.items():
        steps[name] = factory.build()

    step_factories.clear()
    return steps


def get_resources():
    global resource_factories
    resources = {}
    for name, factory in resource_factories.items():
        resources[name] = factory.build()

    resource_factories.clear()
    return resources


def step(name, event: str | None = None):
    def decorator(func):
        global step_factories
        short_name = name.split("/")[-1]
        category = "/".join(name.split("/")[:-1])
        factory = step_factories.get(short_name) or StepClassFactory(
            short_name, category
        )

        while isinstance(func, DecoratorFunction):
            func.fn(factory, **func.kwargs)
            func = func.next

        if event is not None:
            factory.event(event, func)
        else:
            if factory.BaseClass == steps.Step:
                factory.event("on_note", func)
            elif factory.BaseClass == steps.BatchStep:
                factory.event("on_item_batch", func)
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
        def set_p(factory: NodeClassFactory):
            factory.param(name, type, cast_as, default, required, description)

        return DecoratorFunction(func, set_p)

    return decorator


def event(event: str, event_fn: callable):
    def decorator(func):
        def set_event(factory: StepClassFactory):
            factory.event(event, event_fn)

        return DecoratorFunction(func, set_event)

    return decorator


def source(is_generator=True):
    def decorator(func):
        def set_source(factory: StepClassFactory):
            factory.source(is_generator)

        return DecoratorFunction(func, set_source)

    return decorator


def output(*outputs: List[str]):
    def decorator(func):
        def set_output(factory: StepClassFactory):
            factory.output(outputs)

        return DecoratorFunction(func, set_output)

    return decorator


def batch(batch_size: int | None = None, item_key: str | None = None, *, load_fn=None):
    def decorator(func):
        def set_batch(factory: StepClassFactory):
            factory.batch(batch_size, item_key, load_fn)

        return DecoratorFunction(func, set_batch)

    return decorator


def resource(name):
    def decorator(func):
        global resource_factories
        short_name = name.split("/")[-1]
        category = "/".join(name.split("/")[:-1])
        factory = resource_factories.get(short_name) or ResourceClassFactory(
            short_name, category
        )

        while isinstance(func, DecoratorFunction):
            func.fn(factory, **func.kwargs)
            func = func.next

        factory.event("value", func)
        resource_factories[short_name] = factory

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator

import graphbook.steps as steps
import graphbook.resources as resources
from typing import List, Dict
import abc
from graphbook.utils import transform_function_string


class NodeClassFactory:
    def __init__(self, name, category, BaseClass):
        self.name = name
        self.category = category
        self.BaseClass = BaseClass
        self.Parameters = {}
        self.parameter_type_casts = {}
        self.events = {}
        self.docstring = ""

    def event(self, event, func):
        self.events[event] = func

    def doc(self, docstring):
        self.docstring = docstring

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
            if cast_as is None:
                # Default casts
                if type == "function":
                    self.parameter_type_casts[name] = transform_function_string
                if type == "int":
                    self.parameter_type_casts[name] = int

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
        self, default_batch_size: int, default_item_key: str, load_fn=None, dump_fn=None
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
        if dump_fn is not None:
            self.event("dump_fn", dump_fn)

    def prompt(self, get_prompt=None):
        self.BaseClass = steps.PromptStep
        if get_prompt is not None:
            self.event("get_prompt", get_prompt)

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
        newclass.__doc__ = self.docstring
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
        newclass.__doc__ = self.docstring
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
    """
    Marks a function as belonging to a step method.
    Use this decorator if you want to create a new step node or attach new functions as events to an existing step node.

    Args:
        name (str): The name of the step including the category
        event (str): The event that the function should be called on.
            Default is ``on_note``, ``on_item_batch`` if it is a BatchStep, and ``load`` if it is a SourceStep.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("Custom/Simple/MyStep")
            def my_step(ctx, note):
                note["value"] = 42
    """

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
            elif factory.BaseClass == steps.PromptStep:
                factory.event("on_prompt_response", func)
            else:
                factory.event("load", func)

        factory.doc(func.__doc__)
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
    """
    Assigns a parameter to a step or resource.
    Graphbook's web UI will display the parameter as a widget and supply the parameter as kwargs to the step or resource's ``__init__`` event.
    If the type is a *function*, the parameter will be cast as a function using ``transform_function_string()``.

    Args:
        name (str): The name of the parameter
        type (str): The type of the parameter. Can be one of: *string*, *number*, *boolean*, *function*, or *resource*, *dict*, *list[string]*, *list[number]*, *list[boolean]*, *list[function]*.
        default (Any): The default value of the parameter.
        required (bool): Whether the parameter is required.
        description (str): A description of the parameter.
        cast_as (type | callable): A function or class type to cast the parameter to a specific type.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("SimpleStep")
            @param("value", "number", default=42, description="The value to set")
            def my_step(ctx, note):
                note["value"] = ctx.value

            @step("Foo")
            @param("param1", "string", default="foo")
            @param("param2", "function")
            def my_step(ctx, note):
                note["value"] += ctx.param1
                note["processed"] = ctx.param2(note["value"])
    """

    def decorator(func):
        def set_p(factory: NodeClassFactory):
            factory.param(name, type, cast_as, default, required, description)

        return DecoratorFunction(func, set_p)

    return decorator


def event(event: str, event_fn: callable):
    """
    Assigns a callable function as an event i.e. a lifecycle method to a step.
    Graphbook's web UI will display the parameter as a widget and supply the parameter as kwargs to the step or resource's ``__init__`` event.

    Args:
        event (str): The name of the event
        event_fn (callable): The function to call when the event is triggered.

    Examples:
        .. highlight:: python
        .. code-block:: python

            def init(ctx, **kwargs):
                ctx.num_processed = 0

            def on_clear(ctx):
                ctx.num_processed = 0

            @step("StatefulStep")
            @event("__init__", init)
            @event("on_clear", on_clear)
            def my_step(ctx, note):
                ctx.num_processed += 1
                note["num_processed"] = ctx.num_processed
    """

    def decorator(func):
        def set_event(factory: StepClassFactory):
            factory.event(event, event_fn)

        return DecoratorFunction(func, set_event)

    return decorator


def source(is_generator=True):
    """
    Marks a step function as a SourceStep.
    Use this decorator if this step requires no input step and creates Notes to be processed by the rest of the graph.

    Args:
        is_generator (bool): Whether the assigned function is a generator function. Default is true. This means that the function is expected to yield Notes.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("LoadData")
            @source()
            @param("path", "string", description="The path to the data")
            def my_data(ctx, note):
                files = os.listdir(ctx.path)
                for file in files:
                    file = os.path.join(ctx.path, file)
                    with open(file) as f:
                        yield Note({"data": f.read()})
    """

    def decorator(func):
        def set_source(factory: StepClassFactory):
            factory.source(is_generator)

        return DecoratorFunction(func, set_source)

    return decorator


def output(*outputs: List[str]):
    """
    Assigns extra outputs slots to a step.
    By default, Graphbook will assign the step an output slot name "out".
    When using this decorator, you will get rid of the default output slot "out" and replace it with your own.

    Args:
        outputs (str...): A sequence of strings representing the names of the output slots.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("Custom/MyStep", event="forward_note")
            @output("Good", "Bad")
            def evaluate(ctx, note):
                if note["value"] > 0:
                    return "Good"
                else:
                    return "Bad"
    """

    def decorator(func):
        def set_output(factory: StepClassFactory):
            factory.output(outputs)

        return DecoratorFunction(func, set_output)

    return decorator


def batch(batch_size: int = 8, item_key: str = "", *, load_fn=None, dump_fn=None):
    """
    Marks a step function as a BatchStep which can interface with the worker pool to load, batch, and dump data such as images and PyTorch Tensors.
    This will also assign the parameters *batch_size* and *item_key* to the step.
    The decorated function will by default be called on the event ``on_item_batch``.

    Args:
        batch_size (int): The default batch size to use when batching data.
        item_key (str): The expected key in the Note to use for batching. Will be used to find the value of the item to batch.
        load_fn (callable): A function to load the data. This function should take the context and an item and return the loaded data.
        dump_fn (callable): A function to dump the data. This function should take the context and the data and return the dumped data.

    Examples:
        .. highlight:: python
        .. code-block:: python

            def load_fn(ctx, item: dict) -> torch.Tensor:
                im = Image.open(item["value"])
                image = F.to_tensor(im)
                return image

            def dump_fn(ctx, data: torch.Tensor, path: str):
                im = F.to_pil_image(data)
                im.save(path)

            @step("ModelTask")
            @batch(load_fn=load_fn, dump_fn=dump_fn)
            @param("model", "resource")
            def task(ctx, note):
                prediction = ctx.model(note["value"])
                note["prediction"] = prediction
    """

    def decorator(func):
        def set_batch(factory: StepClassFactory):
            factory.batch(batch_size, item_key, load_fn)

        return DecoratorFunction(func, set_batch)

    return decorator


def resource(name):
    """
    Marks a function as a resource that returns an object that can be used by other steps or resources.

    Args:
        name (str): The name of the resource including the category.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @resource("Custom/MyResource")
            @param("model_path", "string", description="The path to the resource")
            @param("fp16", "boolean", default=False, description="Whether to use FP16")
            def my_resource(ctx):
                model = load_model(ctx.model_path, fp16=ctx.fp16)
                return model
    """

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
        factory.doc(func.__doc__)
        resource_factories[short_name] = factory

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def prompt(get_prompt: callable = None):
    """
    Marks a function as a step that is capable of prompting the user.
    This is useful for interactive workflows where data labeling, model evaluation, or any other human input is required.
    Events ``get_prompt(ctx, note: Note)`` and ``on_prompt_response(ctx, note: Note, response: Any)`` are required to be implemented.
    The decorator accepts the ``get_prompt`` function that returns a prompt to display to the user.
    If nothing is passed as an argument, a ``bool_prompt`` will be used by default.
    If the function returns **None** on any given note, no prompt will be displayed for that note allowing for conditional prompts based on the note's content.
    Available prompts are located in the ``graphbook.prompts`` module.
    The function that this decorator decorates is ``on_prompt_response`` and will be called when a response to a prompt is obtained from a user.
    Once the prompt is handled, the execution lifecycle of the Step will proceed, normally.

    Args:
        get_prompt (callable): A function that returns a prompt. Default is ``bool_prompt``.

    Examples:
        .. highlight:: python
        .. code-block:: python

            def dog_or_cat(ctx, note: Note):
                return selection_prompt(note, choices=["dog", "cat"], show_images=True)


            @step("Prompts/Label")
            @prompt(dog_or_cat)
            def label_images(ctx, note: Note, response: str):
                note["label"] = response


            def corrective_prompt(ctx, note: Note):
                if note["prediction_confidence"] < 0.65:
                    return bool_prompt(
                        note,
                        msg=f"Model prediction ({note['pred']}) was uncertain. Is its prediction correct?",
                        show_images=True,
                    )
                else:
                    return None


            @step("Prompts/CorrectModelLabel")
            @prompt(corrective_prompt)
            def correct_model_labels(ctx, note: Note, response: bool):
                if response:
                    ctx.log("Model is correct!")
                    note["label"] = note["pred"]
                else:
                    ctx.log("Model is incorrect!")
                    if note["pred"] == "dog":
                        note["label"] = "cat"
                    else:
                        note["label"] = "dog"
    """
    def decorator(func):
        def set_prompt(factory: StepClassFactory):
            factory.prompt(get_prompt)

        return DecoratorFunction(func, set_prompt)

    return decorator

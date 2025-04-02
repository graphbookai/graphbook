from . import steps, resources
from typing import List, Optional, Union
from .utils import transform_function_string
from copy import deepcopy


def create_type(base):
    """
    Creates a new type that inherits from the base class.
    This is used to create a new class at runtime with the same attributes as the base class.
    """
    child_class_dict = dict(base.__dict__)
    del child_class_dict["__weakref__"]
    del child_class_dict["__dict__"]
    return type("temp", (base,), {**deepcopy(child_class_dict), "build_meta": {}})


def switch_parent(child_class, parent_class):
    """
    Switches the parent class of a child class to a new parent class, so that we
    can change the parent class of a class at runtime.
    """
    child_class_dict = dict(child_class.__dict__)
    # Just copy vars
    for key, value in list(child_class_dict.items()):
        if callable(value):
            del child_class_dict[key]
    child_class = type(
        child_class.__name__,
        (parent_class,),
        {**deepcopy(child_class_dict)},
    )

    return child_class


class DecoratorFunction:
    def __init__(self, next, fn, **kwargs):
        self.next = next
        self.fn = fn
        self.kwargs = kwargs


def step(name: Optional[str] = None, event: Optional[str] = None):
    """
    Marks a function as belonging to a step method.
    Use this decorator if you want to create a new step node or attach new functions as events to an existing step node.

    Args:
        name (str): The name of the step including the category
        event (str): The event that the function should be called on.
            Default is ``on_data``, ``on_item_batch`` if it is a BatchStep, and ``load`` if it is a SourceStep.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("Custom/Simple/MyStep")
            def my_step(ctx, data):
                data["value"] = 42
    """

    def decorator(func):
        cls = create_type(steps.Step)
        cls.build_meta["main_func"] = "on_data" if event is None else event

        def super_call(self, **kwargs):
            steps.Step.__init__(self)

        cls.build_meta["super_call"] = super_call

        while isinstance(func, DecoratorFunction):
            cls = func.fn(cls, **func.kwargs)
            func = func.next

        if name is None:
            short_name = func.__name__
            category = ""
        else:
            short_name = name.split("/")[-1]
            category = "/".join(name.split("/")[:-1])

        cls.__name__ = short_name
        cls.__qualname__ = short_name
        cls.__module__ = func.__module__
        cls.__doc__ = func.__doc__
        cls.Category = category

        super_call = cls.build_meta.get("super_call")
        init_call = cls.build_meta.get("init_call")

        def cls_init(self, **kwargs):
            super_call(self, **kwargs)
            for key, param in self.Parameters.items():
                value = kwargs.get(key) or param.get("default")
                if value is None and param.get("required"):
                    raise ValueError(f"Parameter {key} is required")
                cast_as = self.build_meta["parameter_type_casts"][key]
                if cast_as is not None:
                    value = cast_as(value)
                setattr(self, key, value)
            if init_call:
                init_call(self, **kwargs)

        setattr(cls, "__init__", cls_init)
        setattr(cls, cls.build_meta["main_func"], func)

        return cls

    return decorator


def param(
    name: str,
    type: str,
    *,
    default=None,
    required: bool = False,
    description: str = "",
    cast_as: Optional[type] = None,
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
        cast_as (Optional[Union[type, callable]]): A function or class type to cast the parameter to a specific type.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("SimpleStep")
            @param("value", "number", default=42, description="The value to set")
            def my_step(ctx, data):
                data["value"] = ctx.value

            @step("Foo")
            @param("param1", "string", default="foo")
            @param("param2", "function")
            def my_step(ctx, data):
                data["value"] += ctx.param1
                data["processed"] = ctx.param2(data["value"])
    """

    def decorator(func):
        def set_p(node_class: Union[steps.Step, resources.Resource]):
            node_class.Parameters[name] = {
                "type": type,
                "default": default,
                "required": required,
                "description": description,
            }
            if node_class.build_meta.get("parameter_type_casts") is None:
                node_class.build_meta["parameter_type_casts"] = {}

            # Set to c, to avoid a "cast_as referenced before assignment error"
            c = cast_as
            if c is None:
                # Default casts
                if type == "function":
                    c = transform_function_string
                if type == "int":
                    c = int

            node_class.build_meta["parameter_type_casts"][name] = c
            return node_class

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
            def my_step(ctx, data):
                ctx.num_processed += 1
                data["num_processed"] = ctx.num_processed
    """

    def decorator(func):
        def set_event(node_class):
            if event == "__init__":
                node_class.build_meta["init_call"] = event_fn
            else:
                setattr(node_class, event, event_fn)
            return node_class

        return DecoratorFunction(func, set_event)

    return decorator


def source(is_generator=True):
    """
    Marks a step function as a SourceStep.
    Use this decorator if this step requires no input step and loads data to be processed by the rest of the graph.

    Args:
        is_generator (bool): Whether the assigned function is a generator function. Default is true. This means that the function is expected to have yield statements.

    Examples:
        .. highlight:: python
        .. code-block:: python

            @step("LoadData")
            @source()
            @param("path", "string", description="The path to the data")
            def my_data(ctx):
                files = os.listdir(ctx.path)
                for file in files:
                    file = os.path.join(ctx.path, file)
                    with open(file) as f:
                        yield {"out": {"data": f.read()}}
    """

    def decorator(func):
        def set_source(step_class: steps.Step):
            base_class = steps.GeneratorSourceStep if is_generator else steps.SourceStep
            step_class = switch_parent(
                step_class,
                base_class,
            )
            step_class.build_meta["main_func"] = "load"

            def super_call(self, **kwargs):
                base_class.__init__(self)

            step_class.build_meta["super_call"] = super_call

            return step_class

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

            @step("Custom/MyStep", event="route")
            @output("Good", "Bad")
            def evaluate(ctx, data):
                if data["value"] > 0:
                    return "Good"
                else:
                    return "Bad"
    """

    def decorator(func):
        def set_output(step_class: steps.Step):
            build_meta = step_class.build_meta
            if not build_meta.get("is_outputs_specified"):
                build_meta["is_outputs_specified"] = True
                step_class.Outputs = []
            step_class.Outputs.extend(outputs)
            return step_class

        return DecoratorFunction(func, set_output)

    return decorator


def batch(batch_size: int = 8, item_key: str = "", *, load_fn=None, dump_fn=None):
    """
    Marks a step function as a BatchStep which can interface with the worker pool to load, batch, and dump data such as images and PyTorch Tensors.
    This will also assign the parameters *batch_size* and *item_key* to the step.
    The decorated function will by default be called on the event ``on_item_batch``.

    Args:
        batch_size (int): The default batch size to use when batching data.
        item_key (str): The expected key in the input data to use for batching. Will be used to find the value of the item to batch.
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
            def task(ctx, data):
                prediction = ctx.model(data["value"])
                data["prediction"] = prediction
    """

    def decorator(func):
        def set_batch(step_class):
            step_class = switch_parent(step_class, steps.BatchStep)
            step_class.Parameters["batch_size"] = {
                "type": "number",
                "default": batch_size,
                "required": True,
                "description": "The size of the batch to be loaded",
            }
            step_class.Parameters["item_key"] = {
                "type": "string",
                "default": item_key,
                "required": True,
                "description": "The key to use for batching",
            }

            if load_fn is not None:
                setattr(step_class, "load_fn", load_fn)
            if dump_fn is not None:
                setattr(step_class, "dump_fn", dump_fn)

            step_class.build_meta["main_func"] = "on_item_batch"

            def super_call(self, **kwargs):
                steps.BatchStep.__init__(
                    self, batch_size=kwargs["batch_size"], item_key=kwargs["item_key"]
                )

            step_class.build_meta["super_call"] = super_call
            return step_class

        return DecoratorFunction(func, set_batch)

    return decorator


def resource(name: Optional[str] = None):
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
        cls = create_type(resources.Resource)
        cls.Parameters = (
            {}
        )  # since resources.Resource already starts off with {"val": {...}}
        cls.build_meta["main_func"] = "value"

        def super_call(self, **kwargs):
            steps.Step.__init__(self)

        cls.build_meta["super_call"] = super_call

        while isinstance(func, DecoratorFunction):
            cls = func.fn(cls, **func.kwargs)
            func = func.next

        if name is None:
            short_name = func.__name__
            category = ""
        else:
            short_name = name.split("/")[-1]
            category = "/".join(name.split("/")[:-1])

        cls.__name__ = short_name
        cls.__qualname__ = short_name
        cls.__module__ = func.__module__
        cls.__doc__ = func.__doc__
        cls.Category = category

        super_call = cls.build_meta.get("super_call")
        init_call = cls.build_meta.get("init_call")

        def cls_init(self, **kwargs):
            super_call(self, **kwargs)
            for key, param in self.Parameters.items():
                value = kwargs.get(key) or param.get("default")
                if value is None and param.get("required"):
                    raise ValueError(f"Parameter {key} is required")
                cast_as = self.build_meta["parameter_type_casts"][key]
                if cast_as is not None:
                    value = cast_as(value)
                setattr(self, key, value)
            if init_call:
                init_call(self, **kwargs)

        setattr(cls, "__init__", cls_init)
        setattr(cls, cls.build_meta["main_func"], func)

        return cls

    return decorator


def prompt(get_prompt: callable = None):
    """
    Marks a function as a step that is capable of prompting the user.
    This is useful for interactive workflows where data labeling, model evaluation, or any other human input is required.
    Events ``get_prompt(ctx, data: Any)`` and ``on_prompt_response(ctx, data: Any, response: Any)`` are required to be implemented.
    The decorator accepts the ``get_prompt`` function that returns a prompt to display to the user.
    If nothing is passed as an argument, a ``bool_prompt`` will be used by default.
    If the function returns **None** on any given data, no prompt will be displayed for it allowing for conditional prompts.
    Available prompts are located in the ``graphbook.prompts`` module.
    The function that this decorator decorates is ``on_prompt_response`` and will be called when a response to a prompt is obtained from a user.
    Once the prompt is handled, the execution lifecycle of the Step will proceed, normally.

    Args:
        get_prompt (callable): A function that returns a prompt. Default is ``bool_prompt``.

    Examples:
        .. highlight:: python
        .. code-block:: python

            def dog_or_cat(ctx, data: Any):
                return selection_prompt(data, choices=["dog", "cat"], show_images=True)


            @step("Prompts/Label")
            @prompt(dog_or_cat)
            def label_images(ctx, data: Any, response: str):
                data["label"] = response


            def corrective_prompt(ctx, data: Any):
                if data["prediction_confidence"] < 0.65:
                    return bool_prompt(
                        data,
                        msg=f"Model prediction ({data['pred']}) was uncertain. Is its prediction correct?",
                        show_images=True,
                    )
                else:
                    return None


            @step("Prompts/CorrectModelLabel")
            @prompt(corrective_prompt)
            def correct_model_labels(ctx, data: Any, response: bool):
                if response:
                    ctx.log("Model is correct!")
                    data["label"] = data["pred"]
                else:
                    ctx.log("Model is incorrect!")
                    if data["pred"] == "dog":
                        data["label"] = "cat"
                    else:
                        data["label"] = "dog"
    """

    def decorator(func):
        def set_prompt(step_class: steps.Step):
            step_class = switch_parent(step_class, steps.PromptStep)
            if get_prompt is not None:
                step_class.get_prompt = get_prompt

            step_class.build_meta["main_func"] = "on_prompt_response"

            def super_call(self, **kwargs):
                steps.PromptStep.__init__(self)

            step_class.build_meta["super_call"] = super_call

            return step_class

        return DecoratorFunction(func, set_prompt)

    return decorator

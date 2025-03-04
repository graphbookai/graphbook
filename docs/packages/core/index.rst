.. _Core:

Core
####

.. rst-class:: lead

    Introducing Graphbook Core, the package that provides the basics to building ML apps. 


Graphbook Core contains the basic building blocks for building ML applications in Graphbook.
It provides an API for building custom nodes (i.e., steps and resources) for building observable, interactive, and scalable ML applications.

Getting Started
===============

To get started, make sure Graphbook is installed (e.g ``pip install graphbook``). See :ref:`Installing` for more installation options.


Workflow files can be written as **.json** or **.py** files, so it's recommended to track your workflow files and custom nodes in a version control system like Git.
Inside of an empty directory, you can begin like so:


.. code-block:: console

    $ mkdir my_graphbook_project
    $ cd my_graphbook_project
    $ git init
    $ graphbook

Executing ``graphbook`` starts the Graphbook server and automatically creates the directory structure as follows:

::

    my_graphbook_project
    └── workflow
       ├── custom_nodes
       └── docs

All of your custom nodes should be located inside of `workflow/custom_nodes`.
Graphbook is tracking that directory for any files ending with **.py** and will automatically detect classes that inherit from **Step** or **Resource** and functions defined and decorated with **@step** or **@resource**.

Navigate to http://localhost:8005 in your browser to start building ML workflows.


Workflows
=========

Keep in mind that when working with Graphbook, the development cycle in building a workflow can be illustrated in a few simple steps:

#. **Build in Python**

    Write processing nodes using Python in your favorite code editor

#. **Assemble in Graphbook**

    Assemble an ML workflow in the Graphbook web UI with your own processing nodes.
    Note: as of v0.12.0, you can also create workflows in Python. See :ref:`Python Workflows`.

#. **Execute**

    Run, monitor, and adjust parameters in your workflow

Go into the Graphbook UI (http://localhost:8005), and create a new workflow by adding a new **.json** file.

.. warning::

    Do not try to create the .json file outside of the web UI.
    Graphbook needs the .json file to be structured specifically to properly serialize the graph and will create the file with such structure if you create it through the UI.

This is where you can create your workflows.
When you modify your workflow, the changes are automatically saved to the **.json** file.
It is recommended to regularly commit the **.json** file to your version control system.

Steps
=====

Inside of your custom nodes directory, create a new Python file called `my_first_nodes.py`, and create the below step inside of it:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_nodes.py

            from graphbook import step, param, output, event
            import random

            @step("MyStep")
            def my_first_step(ctx, data: dict):
                data["message"] = "Hello, World!"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_nodes.py

            from graphbook.steps import Step
            import random

            class MyStep(Step):
                RequiresInput = True
                Parameters = {}
                Outputs = ["out"]
                Category = ""
                def __init__(self, prob):
                    super().__init__()
                    self.prob = prob

                def on_data(self, data: dict):
                    data["message"] = "Hello, World!"

In the above, we did the following:

#. We named our step "MyStep"
#. We defined a method called ``my_first_step`` which simply sets "message" with "Hello, World!" inside the incoming dict.

If you're building steps the recommended way, you can observe that the step also has a context ``ctx``.
This is essentially the ``self`` object (the underlying class instance) since all steps are just classes that inherit from the base class :class:`graphbook.steps.Step`.
With decorators, you are actually creating a new Step class with guardrails to prevent you from making common mistakes.

You can provide implementations for any of the methods/events listed in :class:`graphbook.steps.Step`.

You can add this step to your workflow by right clicking the pane, and add a new Step node and select `MyStep` from the dropdown (Add Step > MyStep).
Notice how your inputs, parameters, and outputs are automatically populated.


Load Data
=========

Source steps are steps that generate data.
They are the starting points of your workflow.
You can create a source step by using the :func:`graphbook.source` decorator or by inheriting from the class :class:`graphbook.steps.GeneratorSourceStep`.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_source.py

            from graphbook step, source
            import json

            @step("MySource")
            @source()
            def my_first_source(ctx):
                with open("path/to/data.json") as f:
                    data = json.load(f)
                    for item in data:
                        yield item

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_source.py

            from graphbook.steps import GeneratorSourceStep
            
            class MySource(GeneratorSourceStep):
                RequiresInput = False
                Parameters = {}
                Outputs = ["out"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def load(self):
                    with open("path/to/data.json") as f:
                        data = json.load(f)
                        for item in data:
                            yield item

.. seealso::

    :ref:`Load Images` for more advanced topics on loading images.

Parameters
==========

Parameters are configurable options to nodes which appear on the node in the web UI and can be changed by the user.
You can add parameters to your steps by using the :func:`graphbook.param` decorator or by adding to the dictionary called ``Parameters`` in the class-based nodes.
There exists a number of parameter types such as "string", "number", "boolean".

.. seealso::
    
    A list of :ref:`Available Parameters<Available Parameters>`.

Below shows an example for string and number parameters.
Multiple parameters can be used at the same time:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, param

            @step("MyStep")
            @param("message", type="string", default="Hello, World!")
            @param("offset", type="number", default=0)
            def my_step(ctx, data: dict):
                my_message = ctx.message
                my_offset = ctx.offset

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook.steps import Step
            
            class MyStep(Step):
                RequiresInput = True
                Parameters = {
                    "message": {
                        "type": "string",
                        "default": "Hello, World!"
                    },
                    "offset": {
                        "type": "number",
                        "default": 0
                    }
                }
                Outputs = ["out"]
                Category = ""
                def __init__(self, message, offset):
                    super().__init__()
                    self.message = message
                    self.offset = offset

When using decorators, you don't need to manually assign them to the context ``ctx``.

Casting
*******

When you use the parameter in the function, you can cast it to a specific type.
Sometimes, you want to cast the parameter to a specific type or pass it into a custom function before Graphbook makes the assignment to the context.

.. code-block:: python

    @step("MyStep")
    @param("dimension", type="number", default=0, cast_as=int)
    def my_step(ctx, data: dict):
        mean = data["tensor"].mean(dim=ctx.dimension)

If your parameter is of type "function", you don't need to cast it when using decorators.
The Python function automatically gets interpreted using :func:`graphbook.utils.transform_function_string`.

.. code-block:: python

    @step("MyStep")
    @param("custom_fn", type="function")
    def my_step(ctx, data: dict):
        ctx.custom_fn(data["value"])

Outputs
=======

Steps can have multiple outputs for routing data to different steps or branches of the graph.
By default, a step has one output slot named "out".
You can add more output slots by using the :func:`graphbook.output` decorator or by adding to the list called ``Outputs`` in the class-based nodes.
Then, you may route data based on overriding the method :meth:`graphbook.steps.Step.route`.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, output

            @step("MyStep")
            @output("good", "junk")
            @param("threshold", type="number", default=0.5)
            def my_step(ctx, data: dict):
                if data['value'] > ctx.threshold:
                    return "good"
                return "junk"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook.steps import Step
            
            class MyStep(Step):
                RequiresInput = True
                Parameters = {
                    "threshold": {
                        "type": "number",
                        "default": 0.5
                    }
                }
                Outputs = ["good", "junk"]
                Category = ""
                def __init__(self, threshold):
                    super().__init__()
                    self.threshold = threshold

                def route(self, data: dict) -> str:
                    if data['value'] > self.threshold:
                        return "good"
                    return "junk"

.. seealso::

    :ref:`Filter` for more advanced topics on outputs.

Events
======

Events are methods that are called at specific points in the lifecycle of a step.
You can add events to your steps by using the :func:`graphbook.event` decorator or by just overriding the base class methods.
The event that is decorated by default is the method :meth:`graphbook.steps.Step.on_data`, but this is different depending on the type of step that is inherited.
For example, batch steps (:class:`graphbook.steps.BatchStep`) will override :meth:`graphbook.steps.BatchStep.on_item_batch` by default.
Using :func:`graphbook.event` is an easy way to override a method.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, event

            def route(ctx, data: dict) -> str:
                if data['value'] > 0.5:
                    return "good"
                return "junk"

            @step("MyStep")
            @event("route", route)
            def my_step(ctx, data: dict): # on_data
                ctx.log(data)

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook.steps import Step
            
            class MyStep(Step):
                RequiresInput = True
                Parameters = {}
                Outputs = ["good", "junk"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def on_data(self, data: dict):
                    self.log(data)

                def route(self, data: dict) -> str:
                    if data['value'] > 0.5:
                        return "good"
                    return "junk"

You can also decorate functions with :func:`graphbook.step` multiple times to define different events for the same step.

.. code-block:: python

    @step("MyStep") # on_data
    def my_step(ctx, data: dict):
        ...

    @step("MyStep", event="__init__")
    def my_step_init(ctx):
        ...

    @step("MyStep", event="route")
    def my_step_forward(ctx, data: dict):
        ...

    @step("MyStep", event="on_clear")
    def my_step_clear(ctx):
        ...

.. seealso::

    :class:`graphbook.steps.Step` for more overrideable events.

Resources
=========

Resources are not part of the flow of data but can hold Python objects such as PyTorch models that can be used by other steps.
You can create a resource node by using the :func:`graphbook.resource` decorator or by inheriting from the class :class:`graphbook.resources.Resource`.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_resource.py

            from graphbook import resource
            import torch

            @resource("MyModel")
            def my_first_resource(ctx):
                return torch.nn.Linear(10, 1)

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_resource.py

            from graphbook.resources import Resource
            import torch

            class MyModel(Resource):
                Category = ""
                Parameters = {}
                def __init__(self):
                    super().__init__()
                    self.model = torch.nn.Linear(10, 1).to("cuda")

                def value(self):
                    return self.model

You can access this resource in your step by setting a parameter that accepts a "resource" like so:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            @step("MyStep")
            @param("model", type="resource")
            def my_step(ctx, data: dict):
                model = ctx.model
                ...

    .. tab-item:: class
            
            .. code-block:: python
                :caption: custom_nodes/my_steps.py
    
                class MyStep(Step):
                    RequiresInput = True
                    Parameters = {
                        "model": {"type": "resource"}
                    }
                    Outputs = ["out"]
                    Category = ""
                    def __init__(self, model):
                        super().__init__()
                        self.model = model
    
                    def on_data(self, data: dict) -> str:
                        model = self.model
                        ...

Resources can also have parameters.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_resource.py

            from graphbook import resource, param
            import torch

            @resource("MyModel")
            @param("model_id", type="string", default="model_1")
            def my_first_resource(ctx):
                model = MyPytorchModel()
                model.load_state_dict(torch.load(ctx.model_id)).to("cuda")
                model.eval()
                return model

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_resource.py

            from graphbook.steps import Resource
            import torch

            class MyModel(Resource):
                Category = ""
                Parameters = {
                    "model_id": {"type": "string", "default": "model_1"}
                }
                def __init__(self, model_id):
                    super().__init__()
                    model = MyPytorchModel()
                    model.load_state_dict(torch.load(model_id)).to("cuda")
                    model.eval()
                    self.model = model

                def value(self):
                    return self.model

Categories
==========

You can organize your steps and resources better by assigning them to different categories.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            @step("Custom/MyStep")
            def my_step(ctx, data: dict):
                ...

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            class MyStep(Step):
                ...
                Category = "Custom"
                ...
                
Categories can be multi-leveled with more forward slashes.

.. tab-set::
    
    .. tab-item:: function

        .. code-block:: python

            @step("Custom/Filtering/A")
            def a(ctx, data: dict):
                ...

            @step("Custom/Producer/B")
            def b(ctx, data: dict):
                ...

    .. tab-item:: class
            
        .. code-block:: python

            class A(Step):
                ...
                Category = "Custom/Filtering"
                ...

            class B(Step):
                ...
                Category = "Custom/Producer"
                ...

.. warning::

    Even though 2 steps can have different categories, the step name (basename) must be unique.

    Example:

    .. code-block:: python

        # Not OK

        @step("Custom/Filtering/A")
        def a(ctx, data: dict):
            ...

        @step("Custom/Producer/A") # Will override the previous step
        def b(ctx, data: dict):
            ...


.. toctree::
    :hidden:

    concepts
    guides/index
    examples/index
    reference/index

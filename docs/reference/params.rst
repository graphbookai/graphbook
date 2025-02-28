.. meta::
    :description: Graphbook Reference Documentation for parameters. A list of the available parameter types that can be used in Graphbook.
    :twitter:description: Graphbook Reference Documentation for parameters. A list of the available parameter types that can be used in Graphbook.

Parameters
##########

.. rst-class:: lead

    Graphbook supports a variety of parameter types that can be used to define the inputs and outputs of your steps.

.. _Available Parameters:

Available Parameters
====================

Below is a list of the available values that can be passed as a parameter type in Graphbook:

* string
* number
* boolean
* function
* list[string]
* list[number]
* list[boolean]
* list[function]
* dict
* `resource`\*

\* Any type that is not (string..dict) will default to `resource`.
A resource does not correspond to a widget type but is used to indicate that the parameter accepts resource nodes.

Examples
========

Below shows an example for string and number parameters. Multiple parameters can be used at the same time:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, param

            @step("MyStep")
            @param("message", type="string", default="Hello, World!")
            @param("offset", type="number", default=0)
            def my_step(ctx, data: dict):
                data["message"] = ctx.message
                data["offset"] = ctx.offset

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

                def on_data(self, data: dict) -> str:
                    data["message"] = self.message
                    data["offset"] = self.offset

Below shows an example for a list of strings:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, param

            @step("MyStep")
            @param("cars", type="list[string]", default=["car", "truck"])
            def my_step(ctx, data: dict):
                # Access from ctx.cars
                ...

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook.steps import Step
            
            class MyStep(Step):
                RequiresInput = True
                Parameters = {
                    "cars": {
                        "type": "list[string]",
                        "default": ["car", "truck"]
                    },
                }
                Outputs = ["out"]
                Category = ""
                def __init__(self, cars):
                    super().__init__()
                    self.cars = cars

Below shows an example for a dictionary:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook import step, param

            @step("MyStep")
            @param("car", type="dict", default={
                "make": "Toyota",
                "model": "Camry",
                "price": 25000,
                "in_stock": True
            })
            def my_step(ctx, data: dict):
                # Access from ctx.car
                ...

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_steps.py

            from graphbook.steps import Step
            
            class MyStep(Step):
                RequiresInput = True
                Parameters = {
                    "car": {
                        "type": "dict",
                        "default": {
                            "make": "Toyota",
                            "model": "Camry",
                            "price": 25000,
                            "in_stock": True
                        }
                    },
                }
                Outputs = ["out"]
                Category = ""
                def __init__(self, car):
                    super().__init__()
                    self.car = car

                def on_data(self, data: dict):
                    ...

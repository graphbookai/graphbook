.. meta::
    :description: Follow this simple guide to get started with Graphbook. Learn how to create your first workflow, connect nodes together, and process data.
    :twitter:description: Follow this simple guide to get started with Graphbook. Learn how to create your first workflow, connect nodes together, and process data.

Hello World
###########

This guide will walk you through creating your first Graphbook workflow.
If you have already followed :ref:`Basics`, you should be familiar with the basics of Graphbook, and we recommend that you skip this section.

Create a Step
=============

Inside of your custom nodes directory, create a new Python file called `my_first_nodes.py`, and create the below step inside of it:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_nodes.py

            from graphbook import step, param, output, event
            import random

            def route(data: dict, prob: float) -> str:
                if random.random() < prob:
                    return "A"
                return "B"

            @step("Custom/MyFirstStep") # Category/Name
            @param("prob", type="resource")
            @event("route", route)
            @output("A", "B")
            def my_first_step(ctx, data: float):
                ctx.log(data['message'])

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_nodes.py

            from graphbook.steps import Step
                        import random

            class MyFirstStep(Step):
                RequiresInput = True
                Parameters = {
                    "prob": {
                        "type": "resource"
                    }
                }
                Outputs = ["A", "B"]
                Category = "Custom"
                def __init__(self, prob):
                    super().__init__()
                    self.prob = prob

                def on_data(self, data: dict):
                    self.log(data['message'])

                def route(self, data: dict) -> str:
                    if random.random() < self.prob:
                        return "A"
                    return "B"

This is a simple step that takes a Note as input and logs an item inside of it called "message", and then, it forwards the Note to either of its output slots ("A" or "B") based on the probability provided.
You can provide implementations for any of the methods/events listed in :class:`graphbook.steps.Step`.

Next, go into the Graphbook UI, and create a new workflow by adding a new **.json** file.

.. warning::

    Do not try to create the .json file outside of the web UI.
    Graphbook needs the .json file to be structured specifically to properly serialize the graph and will create the file with such structure if you create it through the UI.

Then, right click the pane, and add a new Step node and select `MyFirstStep` from the dropdown (Add Step > Custom > MyFirstStep).
Notice how your inputs, parameters, and outputs are automatically populated.

.. image:: /_static/1_first_step.png
    :alt: First Step
    :align: center


Create a Source
===============

If you already tried to run the graph, you will notice that you get an error.
That's because you have no inputs and you haven't configured `prob`.
Let's create a Source Step that generates fake data.
Create a new file in the same directory called `my_first_source.py` and add the below code:

.. note::

    The below code doesn't need to be in its own file, but it is good practice to separate your nodes into different files.
    See why :ref:`here<How Nodes Are Reloaded>`.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/my_first_source.py

            from graphbook import step, param, output
            import random

            @step("Custom/MyFirstSource")
            @source()
            @param("message", type="string", default="Hello, World!")
            @output("message")
            def my_first_source(ctx):
                for _ in range(10):
                    yield Note({"message": ctx.message})

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/my_first_source.py

            from graphbook.steps import SourceStep
            
            class MyFirstSource(SourceStep):
                RequiresInput = False
                Parameters = {
                    "message": {
                        "type": "string",
                        "default": "Hello, World!"
                    }
                }
                Outputs = ["message"]
                Category = "Custom"
                def __init__(self, message):
                    super().__init__()
                    self.message = message

                def load(self):
                    return {
                        "message": [Note({"message": self.message}) for _ in range(10)]
                    }

                def route(self, data: dict) -> str:
                    return "message"

This source step generates 10 notes with the message "Hello, World!" by default.
You can change the message in the web UI because we made the message a parameter.
Also, if you do not specify any outputs with ``@output()``, Graphbook will automatically give the step 1 output slot named "out".

Next, add the new node to your workflow by right clicking the pane (Add Step > Custom > MyFirstSource).

Putting Everything Together
===========================

Now, let's connect everything together like so:

.. image:: /_static/2_first_workflow.png
    :alt: First Workflow
    :align: center

Voila! You have successfully created your first workflow, but there's not much ML in this one. Follow the next guide to learn how to use a real ML model in your workflow.

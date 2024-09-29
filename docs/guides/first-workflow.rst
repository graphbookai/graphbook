.. meta::
    :description: Learn how to create your first workflow in Graphbook.
    :twitter:description: Learn how to create your first workflow in Graphbook.

Hello World
###########

All of your custom nodes should be located inside a directory called *custom_nodes* that was automatically created for you upon running ``graphbook``.
Graphbook is tracking that directory for any files ending with **.py** and will automatically detect classes that inherit from **Step** or **Resource** and functions with the **@step** or **@resource** decorator.


Create Your First Step
======================

Inside of your custom nodes directory, create a new Python file called `my_first_nodes.py`, and create the below step inside of it:

.. code-block:: python
    :caption: custom_nodes/my_first_nodes.py

    from graphbook.steps import Step
    from graphbook import Note
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

        def on_after_items(self, note: Note):
            self.log(note['message'])

        def forward_note(self, note: Note) -> str:
            if random.random() < self.prob:
                return "A"
            return "B"

Go into the Graphbook UI, and create a new workflow by adding a new **.json** file.

.. warning::

    Do not try to create the .json file outside of the web UI.
    Graphbook needs the .json file to be structured specifically to properly serialize the graph and will create the file with such structure if you create it through the UI.

Then, right click the pane, and add a new Step node and select `MyFirstStep` from the dropdown (Add Step > Custom > MyFirstStep).
Notice how your inputs, parameters, and outputs are automatically populated.

.. image:: /_static/1_first_step.png
    :alt: First Step
    :align: center


Create Your First Source Step
=============================

If you already tried to run the graph, you will notice that you get an error.
That's because you have no inputs and you haven't configured `prob`.
Let's create a Source Step that generates fake data.
Create a new file in the same directory called `my_first_source.py` and add the below code:

.. note::

    The below code doesn't need to be in its own file, but it is good practice to separate your nodes into different files.
    This is because when you modify the code of a node, Graphbook has to reload the entire Python module, so any node definitions belonging to the same file will also get reloaded.
    When a node gets reloaded, any class instances of that node will be deleted, losing all previous state, and reconstructed as new upon resuming execution of the graph.

.. code-block:: python
    :caption: custom_nodes/my_first_source.py

    from graphbook.steps import SourceStep
    from graphbook import Note

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

        def forward_note(self, note: Note) -> str:
            return "message"

Add the new node to your workflow by right clicking the pane (Add Step > Custom > MyFirstSource).

Create Your First Workflow
==========================

Now, let's connect everything together.

#. Connect the output slot "message" from `MyFirstSource` to the input slot "in" on `MyFirstStep`.
#. Add a NumberResource to your workflow by right clicking the pane (Add Resource > Util > Number).
#. Inside of the value widget enter a number between 0 and 1 (e.g. 0.5).
#. And run it again, observe the logs, and observe the outputs.

.. image:: /_static/2_first_workflow.png
    :alt: First Workflow
    :align: center

Voila! You have successfully created your first workflow, but there's not much ML in this one. Follow the next guide to learn how to use a real ML model in your workflow.

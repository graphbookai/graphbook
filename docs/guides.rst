Guides
###########

Naturally, the development lifecycle of a Graphbook workflow can be illustrated in a few simple steps:

#. **Build in Python**

    Write processing nodes using Python in your favorite code editor

#. **Assemble in Graphbook**

    Assemble an ML workflow in our graph-based editor with your own processing nodes

#. **Execute**

    Run, monitor, and adjust parameters in your workflow

Build Your First ML Workflow
=============================
All of your custom nodes should be located inside a directory that was automatically created for you upon running ``graphbook``.
Graphbook is tracking that directory for any files ending with **.py** and will automatically load classes that inherit from `Step` or `Resource` as custom nodes.
Inside this directory, create a new Python file called `my_first_nodes.py`, and create the below step inside of it:

.. code-block:: python

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
        def __init__(self, id, logger, prob):
            super().__init__(id, logger)
            self.prob = prob

        def on_after_items(self, note: Note):
            self.logger.log(note['message'])

        def forward_note(self, note: Note) -> str:
            if random.random() < self.prob:
                return "A"
            return "B"

Go into the Graphbook UI, create a new workflow by adding a new .json file.
Then, right click the pane, and add a new Step node and select `MyFirstStep` from the dropdown (Add Step > Custom > MyFirstStep).
See how your inputs and outputs are automatically populated.

.. image:: _static/1_first_step.png
    :alt: First Step
    :align: center

Try running the graph.
Notice how you get an error.
That's because you have no inputs and you haven't configured `prob`.
Let's create a Source Step that generates fake data.

.. code-block:: python

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
        def __init__(self, id, logger, message):
            super().__init__(id, logger)
            self.message = message

        def load(self):
            return {
                "message": [Note({"message": self.message}) for _ in range(10)]
            }

        def forward_note(self, note: Note) -> str:
            return "message"

Add the new node to your workflow.
Connect the output slot "message" from `MyFirstSource` to the input slot "in" on `MyFirstStep`.
Then, add a NumberResource to your workflow (Add Resource > Util > Number).
Inside of the value widget enter a number between 0 and 1 (e.g. 0.5).
Now run it again, observe the logs, and observe the outputs.

.. image:: _static/2_first_workflow.png
    :alt: First Workflow
    :align: center


Voila! You have successfully created your first workflow.

.. note::

    More guides are coming soon!

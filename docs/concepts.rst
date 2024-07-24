Concepts
########

Note
*****

Note is the formal name given to the unit of data that flows through a Graphbook workflow. A Note simply holds a dictionary which encapsulates certain information about the thing that is being processed. For example, we can have Notes for all of the world's cars where each Note stores a car’s model, manufacturer, price, and an array of images of the car. 

Step
*****

Step is the one of the two fundamental node types in Graphbook and is a class meant to be extended in Python. Steps are the functional nodes that define the logic of our data processing pipeline. They are fed Notes as input and respond with 0 or more Notes (or an array of notes) at each of its output slots.

Resource
********

Resource is the second fundamental node type in Graphbook and is also an extendible class. It simply holds static information, or is a Python object, that is fed as a parameter to another Resource or Step. A prime example of a Resource is a model. Tip: If a larger object such as a model is being used in multiple Steps in your workflow, it is best to reuse them by putting them in Resources and use the model as a parameter.

Step Lifecycle
**************

A Step goes through lifecycle methods upon processing a Note. The below methods are open for extension and are subject to change in future versions of Graphbook.

#. ``__init__``: The constructor of the Step. This is where you can set up the Step and its parameters. This will not be re-called if a node's code or its parameter values have not changed.
#. ``on_start``: This is called at the start of each graph execution.
#. ``on_before_items``: This is called before the Step processes each Note.
#. ``on_item``: This is called for each item.
#. ``on_item_batch``: This is called for each batch of items. *This only gets called if the Step is a BatchStep.*
#. ``on_after_items``: This is called after the Step processes each Note.
#. ``forward_note``: This is called after the Step processes each Note and is used to route the Note to a certain output slot.
#. ``on_end``: This is called at the end of each graph execution.


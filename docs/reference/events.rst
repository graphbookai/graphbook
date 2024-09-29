.. _sec:events:

Events
######

A step goes through lifecycle methods or events upon processing a note.
If you are creating a custom Step through the functional way, these method names can be passed into the ``@event()`` decorator to customize the behavior of a Step.
If you are creating a custom Step through the class-based method, then you can override the below methods to customize the behavior of the Step within your class.

.. warning::

    All events are subject to change in future versions of Graphbook.

Step 
====

\_\_init\_\_
*************

The constructor of the Step. This is where you can set up the Step and its parameters. This will not be re-called if a node's code or its parameter values have not changed.

on_clear
********

Called when the step is cleared. This is where you can delete any state that the Step has stored.

on_start
********

This is called at the start of each graph execution.


on_note
*******

This is called before the Step processes each note.

on_item
*******

This is called for each item in the note.

on_after_item
**************

This is called after the Step processes each note.

forward_note
*************

This is called after the Step processes each note and is used to route the note to a certain output slot.

on_end
*******

This is called at the end of each graph execution.

**Special Methods**

* ``on_item_batch``: This is called for each batch of items. *This only gets called if the Step is a BatchStep.*
* ``load``: This is called to load notes from a source. *This only gets called if the Step is a SourceStep.*

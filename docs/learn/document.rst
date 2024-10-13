.. meta::
    :description: Learn how to write documentation for individual nodes and workflows, so that it displays right in the UI giving your users the information they need to start working.
    :twitter:description: Learn how to write documentation for individual nodes and workflows, so that it displays right in the UI giving your users the information they need to start working.

Document
########

You can document nodes and workflows in Graphbook, so that it displays right in the UI giving your users the information they need to start working.
Node documentation can be written in docstring, and workflow documentation can be written in a separate .md file.

Node Documentation
==================

You can document your nodes by writing a docstring right beneath the function header or the ``__init__`` function for the class-based nodes.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook import step, param, output, Note

            @step("Filter", event="forward_note")
            @param("threshold", type="number", default=0.5)
            @output("good", "junk")
            def filter(ctx, note: Note):
                """
                Filter notes based on a threshold value.

                Parameters:
                    threshold (number): The threshold value to filter notes.

                Outputs:
                    good (list): Notes that pass the threshold.
                    junk (list): Notes that fail the threshold.
                """
                if note['value'] > ctx.threshold:
                        return { "good": [note] }
                    return { "junk": [note] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook.steps import Step
            from graphbook import Note

            class Filter(Step):
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
                    """
                    Filter notes based on a threshold value.

                    Parameters:
                        threshold (number): The threshold value to filter notes.

                    Outputs:
                        good (list): Notes that pass the threshold.
                        junk (list): Notes that fail the threshold.
                    """
                    super().__init__()
                    self.threshold = threshold

                def forward_note(self, note: Note) -> str:
                    if note['value'] > self.threshold:
                        return { "good": [note] }
                    return { "junk": [note] }

Similarly, for resources:

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook import resource, param

            @resource("Threshold")
            @param("value", type="number", default=0.5)
            def threshold(ctx):
                """
                A threshold value.

                Parameters:
                    value (number): The threshold value.
                """
                return ctx.value

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook.resources import Resource

            class Threshold(Resource):
                Parameters = {
                    "value": {
                        "type": "number",
                        "default": 0.5
                    }
                }
                def __init__(self, value):
                    """
                    A threshold value.

                    Parameters:
                        value (number): The threshold value.
                    """
                    super().__init__(value)

.. _markdown: https://www.markdownguide.org/basic-syntax/

Workflow Documentation
======================

You can document your workflows by writing a .md file in the ``docs/`` directory.
The file should be named after the workflow name, and the content should be written in markdown_ format.

For example:

* Workflow file: ``MyFlow.json``
* Documentation file: ``docs/MyFlow.md``

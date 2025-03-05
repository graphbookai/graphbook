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

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook import step, param, output, Note

            @step("Filter", event="route")
            @param("threshold", type="number", default=0.5)
            @output("good", "junk")
            def filter(ctx, data: dict):
                """
                Filter based on a threshold value.

                Parameters:
                    threshold (number): The threshold value to filter.

                Outputs:
                    good (list): Elements that pass the threshold.
                    junk (list): Elements that fail the threshold.
                """
                if data['value'] > ctx.threshold:
                        return { "good": [data] }
                    return { "junk": [data] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/documented_nodes.py

            from graphbook.steps import Step
            
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
                    Filter based on a threshold value.

                    Parameters:
                        threshold (number): The threshold value to filter.

                    Outputs:
                        good (list): Elements that pass the threshold.
                        junk (list): Elements that fail the threshold.
                    """
                    super().__init__()
                    self.threshold = threshold

                def route(self, data: dict) -> str:
                    if data['value'] > self.threshold:
                        return { "good": [data] }
                    return { "junk": [data] }

Similarly, for resources:

.. tab-set::

    .. tab-item:: function

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

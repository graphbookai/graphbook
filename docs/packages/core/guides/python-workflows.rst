.. meta::
    :description: Define your Graphbook apps and workflows in Python, so that users can adjust parameters, run the workflow, and monitor the results.
    :twitter:description: Define your Graphbook apps and workflows in Python, so that users can adjust parameters, run the workflow, and monitor the results.

.. _Python Workflows:

Python-Defined Workflows
########################

Graphbook allows you to define your workflows in Python.
This is more suited for advanced users who want to have more control over their workflows.
When using a Python-defined workflow, users cannot make structural changes to the graph in the UI.
However, they can still view the graph, adjust parameters, run the workflow, and monitor the results.
Dragging nodes or making any parameters changes will not modify the underlying Python code.

Create a Graph
==============

To define a workflow in Python, create a Python file (e.g., ``my_workflow.py``), and define your workflow in a decorated function belonging to the :class:`graphbook.Graph` class.
For example:

.. code-block:: python
    :caption: my_workflow.py

    import graphbook as gb

    g = gb.Graph()

    @g()
    def _():
        # Define your workflow here

    if __name__ == "__main__":
        graph.run()

Create Nodes
============

To create a step, use the :meth:`graphbook.Graph.step` method.

.. code-block:: python
    :caption: my_workflow.py

    @g()
    def _():
        # ...
        step_0 = g.step(MyStep)

To create a resource, use the :meth:`graphbook.Graph.resource` method.

.. code-block:: python
    :caption: my_workflow.py

    @g()
    def _():
        # ...
        resource_0 = g.resource(MyResource)

Set Parameters
==============

To set parameters, use the :meth:`graphbook.GraphNodeWrapper.param` method.
All nodes, steps and resources, can accept parameters.

.. code-block:: python
    :caption: my_workflow.py

    @g()
    def _():
        # ...
        step_0.param("param_0", 42)
        resource_0.param("param_1", "hello")
        step_0.param("param_1", my_resource) # Also accepts previously defined resources

Order of Configuration
**********************

One of the greatest things about Graphbook is the ease of forwarding your function and class parameters to the UI.
Thus, it is important to mention how parameter values are overwritten.
The order of configuration is as follows:

#. Default values defined within the class or function such as the ones used with :func:`graphbook.param`.
#. Values defined in the Python-defined workflow file will overwrite the default values.
#. Values defined in the UI will overwrite the workflow file ones.

Bind Steps
==========

To bind steps to other steps, use the :meth:`graphbook.GraphStepWrapper.bind` method.
With this method, you can forward an output of one step to the input of another step.

.. code-block:: python
    :caption: my_workflow.py

    @g()
    def _():
        # ...
        step_0.bind(step_1, 'out')


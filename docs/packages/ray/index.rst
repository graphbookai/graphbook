Ray
###

.. meta::
    :description: Learn how to make scalable AI/ML applications with node parameters, monitoring, and performance visualizations using Ray DAGs and Graphbook.
    :twitter:description: Learn how to make scalable AI/ML applications with node parameters, monitoring, and performance visualizations using Ray DAGs and Graphbook.

.. _repo: https://github.com/graphbookai/graphbook

.. rst-class:: lead

    Build distributable Ray Apps with Graphbook!

`Ray <https://github.com/ray-project/ray>`_ is a distributed computing framework that allows you to scale your workflows across multiple machines.
You can build Ray DAGs in Python code using Graphbook's API which provides a wrapper around each node, so that your applications can have the following capabilities:

* **Node Parameters**: Define parameters for each node and configure them in the UI
* **Multi-Output Nodes**: All nodes have named output bindings that can be individually connected to by other nodes
* **Node Documentation**: Docustring from each node class is displayed in the UI
* **Monitoring**: Monitor logging and performance of each node in the UI
* **Output Visualizations**: Visualize the structured Note outputs and images coming from each node.

Although using Ray can make your applications more scalable, there are some limitations to be aware of. See :ref:`Ray_Limitations`.

Getting Started
===============

.. warning::
    This feature is currently in beta. Please report any issues to the repo_.

To get started, install Graphbook along with the graphbook.ray dependencies with:

.. code-block:: console

    $ pip install graphbook[ray]


Using the RayExecutor
=====================

Follow the guide in :ref:`Python Workflows` to create a DAG.
All Graphbook DAGS can be executed using the RayExecutor (:class:`graphbook.ray.RayExecutor`).
To use the RayExecutor, simply pass it to :meth:`graphbook.Graph.run` method like so:

.. code-block:: python
    :caption: myapp.py
    :emphasize-added: 11

    import graphbook as gb
    from graphbook.ray import RayExecutor

    g = gb.Graph()

    @g()
    def _():
        ...

    if __name__ == "__main__":
        g.run(executor=RayExecutor())

To run the app, execute the script:

.. code-block:: bash

    $ python myapp.py


To keep the web app running after execution is finished, you can add the following code to the end of your script:

.. code-block:: python
    :caption: myapp.py
    :emphasize-added: 6-11

    ...

    if __name__ == "__main__":
        g.run(executor=RayExecutor())

        import time

        try:
            time.sleep(999999)
        except KeyboardInterrupt:
            pass

And view your outputs in the web app by navigating to `http://localhost:8005` in your browser.

.. image:: /_static/ray-example.png
    :alt: Example of a Ray App
    :align: center


The RayExecutor will convert all steps and resource into `Ray Actors <https://docs.ray.io/en/latest/ray-core/actors.html>`_ that is compatible with Graphbook.
All node types can be used in Ray DAGs as well except for the ones listed in :ref:`Ray_Limitations`.


.. _Ray_Limitations:

Current Limitations
===================

*
    Nodes created as functions are not yet supported. You must use classes for now.

*
    Execution is synchronous as opposed to the default asynchronous execution that is offered by Graphbook.
    This may slow down troubleshooting of problems that may happen deeper in the DAG.

*
    Only one DAG execution can be constructed at a time.

*
    Currently unsupported features with Ray DAGs, but will be supported in the near future:
    
    * **Prompting**: :class:`graphbook.steps.PromptStep` is not yet supported.

    * **Batching**: :class:`graphbook.steps.BatchStep` is not yet supported but can be easily implemented by the user since execution is synchronous. Feel free to parallelize loading and dumping I/O with regular `ray tasks <https://docs.ray.io/en/latest/ray-core/tasks.html>`_.
    
    * **Streaming/Generator Source Steps**: :class:`graphbook.steps.GeneratorSourceStep` is not yet supported due to the limitations of Ray DAGs. This means you cannot use generators to asynchronously yield data in source nodes when building Ray DAGs with Graphbook.
    
    * **Workflow Documentation**: is not yet supported. Node documentation is still supported.


.. toctree::
    :hidden:

    reference/index

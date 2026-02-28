.. _Beta:

Beta
####

.. rst-class:: lead

    Graphbook Beta — Lightweight observability for Python programs.

Graphbook Beta is a new, lightweight SDK for adding observability to any Python program. Rather than requiring a visual editor or complex node class hierarchy, Beta lets you decorate ordinary Python functions with ``@gb.step()`` and automatically infers the DAG from your runtime call graph. Logs, metrics, inspections, and errors are captured per-node and surfaced through a Rich terminal dashboard, a persistent daemon server, or MCP tools for AI agents.

Key Differences from Core
=========================

Graphbook Core uses a class-based node system (``Step``, ``Resource``, ``BatchStep``) with a visual web UI workflow editor. Beta takes a different approach:

- **Decorator-based**: Just add ``@gb.step()`` to any function — no class inheritance.
- **Automatic DAG inference**: Edges are created when one ``@step`` function calls another. No manual wiring.
- **Zero-config start**: ``import graphbook.beta as gb`` and start decorating. No server required for local mode.
- **MCP-first**: Built with AI agent integration in mind. 15 MCP tools let an AI agent run, monitor, and debug your pipelines.
- **Daemon architecture**: A persistent server (``graphbook-beta serve``) retains state across multiple pipeline runs.

Getting Started
===============

Install graphbook and run your first pipeline:

.. code-block:: console

    $ pip install graphbook
    $ python my_pipeline.py

Write a pipeline:

.. code-block:: python

    import graphbook.beta as gb

    @gb.step()
    def load_data():
        records = [{"id": i, "value": i * 0.5} for i in range(100)]
        gb.log(f"Loaded {len(records)} records")
        return records

    @gb.step()
    def process(records):
        for r in gb.track(records, name="processing"):
            r["value"] *= 2
        gb.log_metric("count", float(len(records)))
        return records

    @gb.step()
    def run():
        data = load_data()
        return process(data)

    if __name__ == "__main__":
        run()

Running this script produces a Rich terminal display showing the DAG structure, execution counts, progress bars, and logs in real time.

Using the Daemon
================

For persistent observability across multiple pipeline runs, start the daemon:

.. code-block:: console

    $ graphbook-beta serve -d
    Graphbook daemon started on localhost:2048 (PID 12345)

    $ graphbook-beta run my_pipeline.py --name "experiment-1"
    Starting pipeline: my_pipeline.py (run_id: experiment-1)
    Pipeline completed successfully (run_id: experiment-1)

    $ graphbook-beta status
    Graphbook daemon: running on port 2048
      Active run: none
      Total runs: 1

    $ graphbook-beta logs --run experiment-1
    $ graphbook-beta errors --run experiment-1
    $ graphbook-beta stop


.. toctree::
    :hidden:

    guide
    reference

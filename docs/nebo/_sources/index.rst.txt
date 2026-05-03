Nebo
####

.. rst-class:: lead

    A modern logging SDK for multi-modal data.

Nebo is a modern logging SDK for multi-modal data. Decorate functions and classes with ``@nb.fn()``, and nebo automatically infers the DAG from your runtime call graph. Logs, metrics, images, audio, text, and errors are captured per-loggable and surfaced through a web UI, a Rich terminal dashboard, a persistent daemon, or MCP tools for AI agents.

.. code-block:: python

    import nebo as nb

    @nb.fn()
    def load_data():
        records = [{"id": i, "value": i * 0.5} for i in range(100)]
        nb.log(f"Loaded {len(records)} records")
        return records

    @nb.fn()
    def process(records):
        for r in nb.track(records, name="processing"):
            r["value"] *= 2
        nb.log_line("count", float(len(records)))
        return records

    @nb.fn()
    def run():
        data = load_data()
        return process(data)

    if __name__ == "__main__":
        run()


Features
********

* **Decorator-based**: Add ``@nb.fn()`` to functions or classes — no inheritance or boilerplate
* **Automatic DAG inference**: Edges are created from data flow between decorated functions
* **Zero-config DAG**: Decorated functions appear in the graph automatically as soon as they run — no explicit registration step
* **Class decoration**: Decorate a class to group its methods under a transparent bounding box in the DAG
* **Multimodal logging**: Text, scalar metrics, images (PIL/numpy/torch), and audio
* **Progress tracking**: ``nb.track()`` for tqdm-like progress bars in the terminal and UI
* **Persistent .nebo files**: Append-only binary log files using MessagePack for crash-safe persistence
* **Web UI**: Real-time DAG visualization, metrics charting, image/audio viewers, and run comparison
* **Agent tracing**: Linear timeline view for agentic workflows
* **Q&A via AI**: Ask questions about runs — nebo delegates to Claude Code CLI via MCP
* **MCP integration**: 17 tools for AI agents to run, monitor, and debug pipelines
* **UI configuration from code**: ``nb.ui()`` and ``@nb.fn(ui={})`` set display defaults
* **Human-in-the-loop**: ``nb.ask()`` pauses the pipeline and prompts the user for input

.. toctree::
   :caption: Docs
   :titlesonly:
   :maxdepth: 3
   :hidden:

   installing
   guide
   reference
   contributing

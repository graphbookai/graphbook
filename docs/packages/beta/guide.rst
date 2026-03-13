.. _Beta Guide:

Guide
#####

This guide walks through building observable Python pipelines with Graphbook Beta, from basic usage to advanced features like configuration injection, MCP integration, and custom logging backends.


Decorating Functions with ``@gb.step()``
=========================================

The ``@gb.step()`` decorator is the core primitive. It registers a function as a node in the pipeline DAG. Edges are inferred from **data flow**: when a step's return value is passed as an argument to another step, an edge is created from the producer to the consumer.

.. code-block:: python

    import graphbook.beta as gb

    @gb.step()
    def load_data():
        """Load raw data."""
        return [1, 2, 3]

    @gb.step()
    def transform(data):
        """Transform data."""
        return [x * 2 for x in data]

    @gb.step()
    def run():
        records = load_data()        # edge: run → load_data (no data dep)
        result = transform(records)  # edge: load_data → transform (data flow)
        return result

When a child step receives no step-produced arguments, the edge falls back to the calling parent step.

The decorator can be used in several forms:

.. code-block:: python

    @gb.step                       # bare (no parentheses)
    @gb.step()                     # empty parentheses
    @gb.step(depends_on=[setup])   # with explicit dependencies


Explicit Dependencies with ``depends_on``
------------------------------------------

Some dependencies cannot be detected automatically — shared mutable state, class attributes, closures, or global variables. Use ``depends_on`` to declare these explicitly:

.. code-block:: python

    @gb.step()
    def setup():
        """Initialize shared resources."""
        ...

    @gb.step(depends_on=[setup])
    def process():
        """Uses resources initialized by setup."""
        ...

``depends_on`` accepts a list of step functions or node ID strings. Explicit dependencies are added alongside any auto-detected data-flow edges.

.. note::

    Graphbook tracks data flow via argument passing (``id()``-based return value tracking). Dependencies through shared mutable state, class attributes, closures, or global variables are **not** automatically detected. Use ``depends_on`` for these cases.


Logging
=======

Graphbook provides several logging functions, all scoped to the currently executing node.

Text Logs
---------

``gb.log(message)`` logs a plain text message:

.. code-block:: python

    @gb.step()
    def train(model, data):
        gb.log("Starting training...")
        for epoch in range(10):
            loss = train_epoch(model, data)
            gb.log(f"Epoch {epoch}: loss={loss:.4f}")

Scalar Metrics
--------------

``gb.log_metric(name, value, step=None)`` logs a scalar metric. Steps are auto-incremented if not provided:

.. code-block:: python

    @gb.step()
    def train(model, data):
        for epoch in range(100):
            loss = train_epoch(model, data)
            accuracy = evaluate(model, data)
            gb.log_metric("loss", loss)
            gb.log_metric("accuracy", accuracy)

Images
------

``gb.log_image(name, image, step=None)`` accepts PIL images, NumPy arrays, or PyTorch tensors:

.. code-block:: python

    @gb.step()
    def augment(image):
        result = apply_transforms(image)
        gb.log_image("augmented", result)
        return result

Audio
-----

``gb.log_audio(name, audio, sr=16000)`` logs audio data as NumPy arrays:

.. code-block:: python

    @gb.step()
    def synthesize(text):
        waveform = tts_model(text)
        gb.log_audio("speech", waveform, sr=22050)
        return waveform

Rich Text
---------

``gb.log_text(name, text)`` logs Markdown or formatted text:

.. code-block:: python

    @gb.step()
    def summarize(stats):
        gb.log_text("report", f"""## Results
    - **Accuracy**: {stats['acc']:.2%}
    - **Loss**: {stats['loss']:.4f}
    """)


Object Inspection
=================

``gb.inspect(obj, name)`` logs metadata about an object without logging the raw data. This is useful for debugging tensor shapes, dtypes, and value ranges:

.. code-block:: python

    @gb.step()
    def forward(model, batch):
        output = model(batch)
        gb.inspect(output, "model_output")
        # Captures: shape, dtype, device, requires_grad, min, max, mean
        return output

For PyTorch tensors, it captures ``shape``, ``dtype``, ``device``, ``requires_grad``, ``min``, ``max``, ``mean``. For NumPy arrays, it captures ``shape``, ``dtype``, ``min``, ``max``, ``mean``. For pandas DataFrames, it captures ``columns`` and ``dtypes``. For any object with ``__len__``, it captures the length.


Progress Tracking
=================

``gb.track(iterable, name, total)`` wraps an iterable for tqdm-like progress tracking. The terminal dashboard renders a live progress bar:

.. code-block:: python

    @gb.step()
    def process(items):
        results = []
        for item in gb.track(items, name="processing"):
            results.append(transform(item))
        return results

If the iterable has a ``__len__``, the total is auto-detected. Otherwise you can pass ``total`` explicitly:

.. code-block:: python

    for batch in gb.track(dataloader, name="training", total=len(dataloader)):
        ...


Configuration Injection
========================

``gb.configure(config)`` sets a global configuration dictionary. Functions decorated with ``@gb.step("key")`` have matching config values injected into their parameters automatically:

.. code-block:: python

    gb.configure({
        "model": {"lr": 0.001, "epochs": 50, "hidden_size": 256},
        "data": {"path": "/data/train", "batch_size": 64},
    })

    @gb.step("model")
    def train(lr: float = 0.01, epochs: int = 10, hidden_size: int = 128):
        # lr=0.001, epochs=50, hidden_size=256 are injected from config["model"]
        ...

    @gb.step("data")
    def load(path: str = ".", batch_size: int = 32):
        # path="/data/train", batch_size=64 are injected from config["data"]
        ...

The config key is the first positional argument to ``@gb.step()``. Only parameters whose names match keys in the config sub-dictionary are injected. Default values are used for any parameters not in the config.


Workflow Description
====================

``gb.md(description)`` sets a Markdown description for the overall workflow. This is visible in MCP tools and the terminal dashboard:

.. code-block:: python

    gb.md("""
    # Image Classification Pipeline

    Loads images from disk, runs inference with a pretrained ResNet,
    and exports predictions to a JSON file.
    """)

Calling ``gb.md()`` multiple times appends to the description.


Human-in-the-Loop
==================

``gb.ask(question, options, timeout)`` pauses the pipeline and prompts the user for input. In server mode, the question is sent via MCP. In local mode, it falls back to a Rich terminal prompt:

.. code-block:: python

    @gb.step()
    def review(predictions):
        answer = gb.ask(
            "Model accuracy is 73%. Continue training?",
            options=["yes", "no", "retrain"]
        )
        if answer == "no":
            return predictions
        elif answer == "retrain":
            return retrain(predictions)
        ...


Execution Modes
===============

Local Mode (Default)
--------------------

When you run a script directly (``python my_pipeline.py``), graphbook operates in local mode. A Rich terminal display shows the DAG, node execution counts, progress bars, and logs. No daemon is required.

Server Mode
-----------

When the daemon is running, events are streamed to it via HTTP. This is activated automatically when using ``graphbook-beta run``, which sets the ``GRAPHBOOK_MODE``, ``GRAPHBOOK_SERVER_PORT``, and ``GRAPHBOOK_RUN_ID`` environment variables.

You can also trigger server mode manually:

.. code-block:: python

    import graphbook.beta as gb
    gb.init(mode="server", port=2048)

Auto Mode
---------

The default mode is ``auto``. On initialization, graphbook checks for a running daemon — if found, it uses server mode; otherwise it falls back to local mode. This is what happens when you call ``gb.init()`` without arguments, or when the ``@step`` decorator triggers auto-initialization from environment variables.


Custom Logging Backends
========================

Implement the ``LoggingBackend`` protocol to route events to external systems (TensorBoard, MLflow, W&B, etc.):

.. code-block:: python

    from graphbook.beta import LoggingBackend

    class TensorBoardBackend:
        def __init__(self, log_dir="runs"):
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(log_dir)

        def on_log(self, node, message, timestamp):
            pass  # TensorBoard doesn't have a text log concept

        def on_metric(self, node, name, value, step):
            self.writer.add_scalar(f"{node}/{name}", value, step)

        def on_image(self, node, name, image_bytes, step):
            pass

        def on_audio(self, node, name, audio_bytes, sr):
            pass

        def on_node_start(self, node, params):
            pass

        def on_node_end(self, node, duration):
            pass

        def flush(self):
            self.writer.flush()

        def close(self):
            self.writer.close()

    gb.init(backends=[TensorBoardBackend()])

Multiple backends can be active simultaneously.


MCP Integration for AI Agents
==============================

Graphbook Beta includes 15 MCP tools that allow AI agents (like Claude) to run, monitor, and debug pipelines. To set up MCP:

1. Start the daemon:

   .. code-block:: console

       $ graphbook-beta serve -d

2. Get the MCP config:

   .. code-block:: console

       $ graphbook-beta mcp

3. Add the printed config to your Claude Desktop or Claude Code MCP configuration.

The MCP tools provide observation (``get_graph``, ``get_node_status``, ``get_logs``, ``get_metrics``, ``get_errors``, ``get_description``, ``inspect_object``) and action (``run_pipeline``, ``stop_pipeline``, ``restart_pipeline``, ``get_run_status``, ``get_run_history``, ``get_source_code``, ``write_source_code``, ``ask_user``) capabilities. An AI agent can use these to autonomously run experiments, diagnose failures, patch code, and iterate.


Complete Example: Data Processing Pipeline
============================================

.. code-block:: python

    import numpy as np
    import graphbook.beta as gb

    gb.md("# Data Processing Pipeline\nGenerate, normalize, filter, and analyze data.")

    gb.configure({
        "data": {"num_samples": 200, "noise": 0.1, "seed": 42},
        "processing": {"method": "standard", "clip_min": -3.0, "clip_max": 3.0},
    })

    @gb.step("data")
    def generate(num_samples: int = 100, noise: float = 0.2, seed: int = 0):
        """Generate synthetic signal data."""
        np.random.seed(seed)
        t = np.linspace(0, 4 * np.pi, num_samples)
        signal = np.sin(t) + noise * np.random.randn(num_samples)
        gb.log(f"Generated {num_samples} samples")
        gb.inspect(signal, "raw_signal")
        return signal

    @gb.step("processing")
    def normalize(data, method: str = "standard", clip_min: float = -5, clip_max: float = 5):
        """Normalize and clip the signal."""
        if method == "standard":
            data = (data - data.mean()) / (data.std() + 1e-8)
        data = np.clip(data, clip_min, clip_max)
        gb.log(f"Normalized with method={method}, clipped to [{clip_min}, {clip_max}]")
        gb.inspect(data, "normalized")
        return data

    @gb.step()
    def analyze(data):
        """Compute statistics on the processed data."""
        stats = {"mean": float(data.mean()), "std": float(data.std()), "n": len(data)}
        gb.log(f"Stats: mean={stats['mean']:.4f}, std={stats['std']:.4f}")
        gb.log_metric("mean", stats["mean"])
        gb.log_metric("std", stats["std"])
        return stats

    @gb.step()
    def run():
        """Main entry point."""
        data = generate()
        normed = normalize(data)
        return analyze(normed)

    if __name__ == "__main__":
        result = run()
        print(result)

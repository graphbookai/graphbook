.. _Guide:

Guide
#####

This guide walks through building observable Python pipelines with Nebo, from basic usage to advanced features like class decoration, persistent log files, MCP integration, and Q&A.


Decorating Functions with ``@nb.fn()``
=======================================

The ``@nb.fn()`` decorator is the core primitive. It registers a function for scope tracking in the pipeline DAG. A node materializes (appears in the DAG) as soon as the decorated function runs for the first time — you do not have to call a logging function to make a node show up. Edges are inferred from **data flow**: when a node's return value is passed as an argument to another node, an edge is created from the producer to the consumer.

.. code-block:: python

    import nebo as nb

    @nb.fn()
    def load_data():
        """Load raw data."""
        nb.log("Loading data")
        return [1, 2, 3]

    @nb.fn()
    def transform(data):
        """Transform data."""
        nb.log(f"Transforming {len(data)} items")
        return [x * 2 for x in data]

    @nb.fn()
    def run():
        records = load_data()
        result = transform(records)  # edge: load_data -> transform (data flow)
        return result

The decorator can be used in several forms:

.. code-block:: python

    @nb.fn                       # bare (no parentheses)
    @nb.fn()                     # empty parentheses
    @nb.fn(depends_on=[setup])   # with explicit dependencies
    @nb.fn(ui={"color": "#34d399"})  # with per-node UI hints


Explicit Dependencies with ``depends_on``
------------------------------------------

Some dependencies cannot be detected automatically — shared mutable state, class attributes, closures, or global variables. Use ``depends_on`` to declare these explicitly:

.. code-block:: python

    @nb.fn()
    def setup():
        """Initialize shared resources."""
        nb.log("Setting up")

    @nb.fn(depends_on=[setup])
    def process():
        """Uses resources initialized by setup."""
        nb.log("Processing")

``depends_on`` accepts a list of decorated functions or node ID strings. Explicit dependencies are added alongside any auto-detected data-flow edges.

.. note::

    Nebo tracks data flow via argument passing (``id()``-based return value tracking). Dependencies through shared mutable state, class attributes, closures, or global variables are **not** automatically detected. Use ``depends_on`` for these cases.


Decorating Classes
===================

``@nb.fn()`` can also be applied to a class. All methods are wrapped with scope tracking. The class itself is never a node — it serves as a visual grouping container (transparent bounding box) in the DAG.

.. code-block:: python

    import nebo as nb

    @nb.fn()
    class DataPipeline:
        def load(self):
            nb.log("Loading data")
            return [1, 2, 3]

        def transform(self, data):
            nb.log(f"Transforming {len(data)} items")
            return [x * 2 for x in data]

        def save(self, data):
            nb.log(f"Saving {len(data)} items")

In the DAG, ``DataPipeline`` appears as a transparent bounding box containing ``load``, ``transform``, and ``save`` as individual nodes.

**Scoping rules:**

- Every method gets its own scope. Logs inside ``transform()`` are scoped to ``DataPipeline.transform``.
- Every method that runs materializes as a node, including silent methods that never call a log function — this keeps dependency chains in the DAG intact even when an intermediate method only orchestrates calls to other nodes.
- If a method also has ``@nb.fn()`` on it, a warning is issued (the decorator is redundant).
- A standalone ``@nb.fn()`` function called from within the class also appears inside the class group.
- A decorated method in an **undecorated** class is a regular standalone node with no bounding box.


The Global loggable
===================

``nb.log``, ``nb.log_line`` (and the other typed ``nb.log_*`` chart
helpers), ``nb.log_image``, and ``nb.log_audio`` all work *outside*
any ``@nb.fn()`` function. Calls made at module scope or from
non-decorated helpers land on the **Global loggable**, identified as
``"__global__"``.

The Global loggable appears as a distinct card at the top of the grid
view (labelled **"List"** on mobile) and is excluded from the DAG view
— it is not a node. Its tabs (Logs, Metrics, Images, Audio) work
identically to any node's tabs.

Example:

.. code-block:: python

    import nebo as nb

    nb.log("environment looks good")           # → Global
    nb.log_line("warmup_heartbeat", 1.0)       # → Global

    @nb.fn()
    def train(): ...


Logging
=======

Nebo provides several logging functions, all scoped to the currently executing node.

Text Logs
---------

``nb.log(message)`` logs a plain text message. Tensor-like objects (NumPy arrays, PyTorch tensors) are auto-formatted with shape, dtype, and statistics:

.. code-block:: python

    @nb.fn()
    def train(model, data):
        nb.log("Starting training...")
        for epoch in range(10):
            loss = train_epoch(model, data)
            nb.log(f"Epoch {epoch}: loss={loss:.4f}")

Metric charts
-------------

Nebo has one logging function per chart type — ``nb.log_line`` for
scalars over time, ``nb.log_bar`` and ``nb.log_pie`` for snapshot
distributions, ``nb.log_histogram`` for labeled distributions, and
``nb.log_scatter`` for labeled 2-D point clouds. The chart type locks
on first emission per ``(loggable, name)`` pair, so reusing a name
with a different ``log_*`` function raises ``ValueError``.

``log_line`` is the only chart type that accumulates over time.
Re-emitting it with the same name appends another step; ``step``
auto-increments if omitted:

.. code-block:: python

    @nb.fn()
    def train(model, data):
        for epoch in range(100):
            loss = train_epoch(model, data)
            accuracy = evaluate(model, data)
            nb.log_line("loss", loss)
            nb.log_line("accuracy", accuracy)

``log_bar``, ``log_pie``, ``log_scatter``, and ``log_histogram`` are
**snapshots** — every re-emission overwrites the prior value. They
don't accept ``step`` or ``tags`` (those concepts only make sense for
line). ``log_scatter`` takes a labeled point dict and lets the UI
toggle each label on or off:

.. code-block:: python

    nb.log_scatter("embed_2d", {
        "inliers":  [(0.1, 0.2), (0.3, 0.4)],
        "outliers": [(2.0, -1.0)],
    })

``log_histogram`` accepts ``{label: list[number]}`` — every label is
its own distribution, all binned against a shared range so overlaps
line up. ``log_scatter`` and ``log_histogram`` also accept
``colors: bool = False``; setting ``colors=True`` distinguishes labels
by palette color (in addition to per-label shapes for scatter), but
is not recommended in comparison views where the palette is reserved
for run identity.

Images
------

``nb.log_image(image, name=None, step=None)`` accepts PIL images, NumPy arrays, or PyTorch tensors:

.. code-block:: python

    @nb.fn()
    def augment(image):
        result = apply_transforms(image)
        nb.log_image(result, name="augmented")
        return result

Audio
-----

``nb.log_audio(audio, sr=16000, name=None)`` logs audio data as NumPy arrays:

.. code-block:: python

    @nb.fn()
    def synthesize(text):
        waveform = tts_model(text)
        nb.log_audio(waveform, sr=22050, name="speech")
        return waveform

Configuration
-------------

``nb.log_cfg(cfg)`` logs configuration for the current node. Values are displayed in the Info tab:

.. code-block:: python

    @nb.fn()
    def train(lr=0.001, epochs=50):
        nb.log_cfg({"lr": lr, "epochs": epochs})
        ...

Multiple ``log_cfg()`` calls within the same node merge their dictionaries.


Progress Tracking
=================

``nb.track(iterable, name, total)`` wraps an iterable for tqdm-like progress tracking. The terminal dashboard and UI render a live progress bar:

.. code-block:: python

    @nb.fn()
    def process(items):
        results = []
        for item in nb.track(items, name="processing"):
            results.append(transform(item))
        return results

If the iterable has a ``__len__``, the total is auto-detected. Otherwise you can pass ``total`` explicitly:

.. code-block:: python

    for batch in nb.track(dataloader, name="training", total=len(dataloader)):
        ...


Workflow Description
====================

``nb.md(description)`` sets a Markdown description for the overall workflow. This is visible in MCP tools and the terminal dashboard:

.. code-block:: python

    nb.md("""
    # Image Classification Pipeline

    Loads images from disk, runs inference with a pretrained ResNet,
    and exports predictions to a JSON file.
    """)

Calling ``nb.md()`` multiple times appends to the description.


Human-in-the-Loop
==================

``nb.ask(question, options, timeout)`` pauses the pipeline and prompts the user for input. In server mode, the question appears in the web UI. In local mode, it falls back to a Rich terminal prompt:

.. code-block:: python

    @nb.fn()
    def review(predictions):
        answer = nb.ask(
            "Model accuracy is 73%. Continue training?",
            options=["yes", "no", "retrain"]
        )
        if answer == "no":
            return predictions
        elif answer == "retrain":
            return retrain(predictions)
        ...


UI Configuration from Code
============================

``nb.ui()`` sets run-level UI defaults. The web UI reads these as defaults that the user can override:

.. code-block:: python

    nb.ui(
        layout="horizontal",     # or "vertical"
        view="dag",              # or "grid"
        minimap=True,            # show minimap
        theme="dark",            # or "light"
    )

Per-node display hints can be set via ``@nb.fn(ui={})``. Supported keys:

- ``color`` (str) — accent color for the node's badge / border.
- ``default_tab`` (str) — which tab opens by default for the node. One of
  ``"logs"``, ``"metrics"``, ``"images"``, ``"audio"``, ``"ask"``. The
  user's clicks always override this preference.

Unknown keys are forwarded verbatim for forward compatibility with
future UI features.

.. code-block:: python

    @nb.fn(ui={"color": "#fb923c"})
    def data_loader():
        nb.log("Loading data")
        ...

    @nb.fn(ui={"default_tab": "metrics"})
    def train(epochs=100):
        for step in range(epochs):
            nb.log_line("loss", compute_loss(step))


Execution Modes
===============

Local Mode (Default)
--------------------

When you run a script directly (``python my_pipeline.py``), nebo operates in local mode. A Rich terminal display shows the DAG, node execution counts, progress bars, and logs. No daemon is required.

Server Mode
-----------

When the daemon is running, events are streamed to it via HTTP. This is activated automatically when using ``nebo run``, which sets the ``NEBO_MODE``, ``NEBO_SERVER_PORT``, and ``NEBO_RUN_ID`` environment variables.

You can also trigger server mode manually:

.. code-block:: python

    import nebo as nb
    nb.init(mode="server", port=7861)

Auto Mode
---------

The default mode is ``auto``. On initialization, nebo checks for a running daemon — if found, it uses server mode; otherwise it falls back to local mode.


Persistent .nebo Files
=======================

Nebo can persist runs to append-only binary ``.nebo`` files using MessagePack. Storage is enabled by default and managed by the daemon.

When the daemon starts, it creates a ``.nebo/`` directory in its working directory. Each run is stored as ``.nebo/<timestamp>_<run_id>.nebo``.

To disable storage for a specific run:

.. code-block:: python

    nb.init(store=False)

To disable storage globally when starting the daemon:

.. code-block:: bash

    nebo serve --no-store

To load a ``.nebo`` file into a *local* daemon for viewing and Q&A:

.. code-block:: bash

    nebo load path/to/run.nebo

To load a file into a *remote* daemon (e.g. one running on a
Hugging Face Space), pass ``--url``. The file is read locally and
its events are replayed through ``/events`` because the remote
daemon can't see your filesystem:

.. code-block:: bash

    nebo load path/to/run.nebo \
        --url https://username-space.hf.space \
        --api-token nb_…

``NEBO_URL`` and ``NEBO_API_TOKEN`` env vars work as defaults so
you don't have to repeat the flags.


MCP Integration for AI Agents
===============================

Nebo includes 21 MCP tools that allow AI agents (like Claude) to
run, monitor, debug, query, and *push data into* pipelines. To set
up MCP:

1. Start the daemon:

   .. code-block:: console

       $ nebo serve -d

2. Get the MCP config:

   .. code-block:: console

       $ nebo mcp

3. Add the printed config to your Claude Desktop or Claude Code MCP configuration.

The tools fall into three buckets:

- **Observation** — ``nebo_get_graph``, ``nebo_get_loggable_status``,
  ``nebo_get_logs``, ``nebo_get_metrics``, ``nebo_get_errors``,
  ``nebo_get_description``.
- **Action / lifecycle** — ``nebo_run_pipeline``, ``nebo_stop_pipeline``,
  ``nebo_restart_pipeline``, ``nebo_get_run_status``,
  ``nebo_get_run_history``, ``nebo_get_source_code``,
  ``nebo_write_source_code``, ``nebo_wait_for_event``,
  ``nebo_ask_user``, ``nebo_load_file``, ``nebo_chat``.
- **Write** — ``nebo_log_metric``, ``nebo_log_image``,
  ``nebo_log_audio``, ``nebo_log_text``. These mirror the SDK's
  ``nb.log_*`` helpers so an external agent can push metrics, media,
  and text into a run without owning the SDK process. URL-based
  media is fetched server-side and persisted via the existing media
  path so runs stay self-contained even when the source URL goes
  stale.

An AI agent can use these to autonomously run experiments, diagnose
failures, patch code, ask questions about runs, and iterate.


Q&A Chat
=========

Nebo supports querying runs using natural language. From the web UI, users can open the Chat tab in the right panel and ask questions like "how did my training run go?" or "what metrics are underperforming?"

The daemon delegates Q&A to Claude Code CLI, spawning it as a subprocess with MCP config pointing back to itself. Claude Code reads the run's state via MCP tools and generates an answer.

This requires Claude Code CLI to be installed on the system where the daemon runs.


Notebook Embedding via ``nb.show()``
======================================

In a Jupyter / IPython context, ``nb.show()`` returns an inline
``<iframe>`` pointing at the running daemon. The slice rendered is
inferred from which kwargs you pass — there is no ``view=``
discriminator. Pick at most one of ``metric`` / ``image`` / ``audio``
/ ``logs`` / ``dag``; pass nothing for the full run dashboard.

.. code-block:: python

    import nebo as nb

    nb.show()                                  # full run
    nb.show(node="train")                      # single node detail
    nb.show(node="train", metric="loss")       # one metric, scoped to a node
    nb.show(metric=True)                       # gallery of all metrics
    nb.show(logs=True)                         # logs panel
    nb.show(dag=True)                          # DAG only

Each call maps to a URL the iframe loads — the same query-param
scheme the dashboard accepts directly:

============================  ====================================
Python                        URL appended to the daemon root
============================  ====================================
``nb.show()``                 ``?run=<id>``
``nb.show(node="t")``         ``?run=<id>&node=t``
``nb.show(metric="loss")``    ``?run=<id>&metric=loss``
``nb.show(metric=True)``      ``?run=<id>&metrics``
``nb.show(image="hero.png")`` ``?run=<id>&image=hero.png``
``nb.show(audio=True)``       ``?run=<id>&audios``
``nb.show(logs=True)``        ``?run=<id>&logs``
``nb.show(dag=True)``         ``?run=<id>&dag``
============================  ====================================

When the daemon enforces auth, append ``&token=…`` to the URL — the
dashboard captures it once on first load, persists it in
localStorage, and strips it from the visible URL via
``replaceState``.


Hosting on Hugging Face Spaces
================================

Nebo's daemon is the same FastAPI app whether it runs on your laptop,
in CI, or on a Hugging Face Space. ``nebo deploy`` bundles a
Docker-SDK Space, sets the necessary secrets, and gives you the
endpoint URL plus a token to share with the SDK.

Install the optional ``deploy`` extra and authenticate:

.. code-block:: bash

    pip install 'nebo[deploy]'
    huggingface-cli login           # writes a token write-scoped for your account

Deploy to a new (or existing) Space:

.. code-block:: bash

    nebo deploy --space-id <user>/nebo-test --from-source

The CLI prints the public URL and a randomly-generated
``NEBO_API_TOKEN``. Save it — the deploy won't show it again. Use
``--api-token <tok>`` to supply your own.

Connect the SDK from anywhere:

.. code-block:: python

    import nebo as nb

    nb.init(
        url="https://<user>-nebo-test.hf.space",
        api_token="nb_…",
    )

    @nb.fn()
    def step():
        nb.log("hello from a remote Space")
        nb.log_line("loss", 0.42)

    step()

Or set ``NEBO_URL`` / ``NEBO_API_TOKEN`` in the environment so the
same script works locally and remotely without a code change.

Access modes
------------

The deployed daemon defaults to **public reads, private writes** —
anyone with the URL can view runs in the dashboard, but only token
holders can push events or control runs. Override with the
``--read`` / ``--write`` flags:

.. code-block:: bash

    nebo deploy --space-id <user>/private-dash \
        --read private --write private \
        --from-source

================  ==========================  ===========================
Mode              ``--read``                  ``--write``
================  ==========================  ===========================
Public dashboard  ``public`` (default)        ``private`` (default)
Private dashboard ``private``                 ``private``
Read-only mirror  ``public``                  ``public``  (no SDK auth)
================  ==========================  ===========================

Embed slices on a website
-------------------------

The same iframe URL scheme used by ``nb.show()`` works against the
deployed Space. Anything that renders HTML can host a live slice:

.. code-block:: html

    <iframe
        src="https://<user>-nebo-test.hf.space/?run=<id>&metric=loss"
        width="100%" height="600">
    </iframe>

For private dashboards, append ``&token=…`` once — the dashboard
caches it for subsequent visits.

Loading a local file into a deployed Space
------------------------------------------

If you have a ``.nebo`` file from a local run and want it visible on
the Space:

.. code-block:: bash

    export NEBO_URL=https://<user>-nebo-test.hf.space
    export NEBO_API_TOKEN=nb_…
    nebo load path/to/run.nebo --url "$NEBO_URL"

The events are read locally and replayed through ``/events`` on the
remote daemon (the daemon's ``POST /load`` only accepts server-side
paths, which don't help when the file is on your laptop).


Complete Example: Data Processing Pipeline
============================================

.. code-block:: python

    import numpy as np
    import nebo as nb

    nb.md("# Data Processing Pipeline\nGenerate, normalize, filter, and analyze data.")

    @nb.fn()
    def generate(num_samples: int = 200, noise: float = 0.1, seed: int = 42):
        """Generate synthetic signal data."""
        nb.log_cfg({"num_samples": num_samples, "noise": noise, "seed": seed})
        np.random.seed(seed)
        t = np.linspace(0, 4 * np.pi, num_samples)
        signal = np.sin(t) + noise * np.random.randn(num_samples)
        nb.log(f"Generated {num_samples} samples")
        return signal

    @nb.fn()
    def normalize(data, method: str = "standard", clip_min: float = -3.0, clip_max: float = 3.0):
        """Normalize and clip the signal."""
        nb.log_cfg({"method": method, "clip_min": clip_min, "clip_max": clip_max})
        if method == "standard":
            data = (data - data.mean()) / (data.std() + 1e-8)
        data = np.clip(data, clip_min, clip_max)
        nb.log(f"Normalized with method={method}, clipped to [{clip_min}, {clip_max}]")
        return data

    @nb.fn()
    def analyze(data):
        """Compute statistics on the processed data."""
        stats = {"mean": float(data.mean()), "std": float(data.std()), "n": len(data)}
        nb.log(f"Stats: mean={stats['mean']:.4f}, std={stats['std']:.4f}")
        nb.log_line("mean", stats["mean"])
        nb.log_line("std", stats["std"])
        return stats

    @nb.fn()
    def run():
        """Main entry point."""
        data = generate()
        normed = normalize(data)
        return analyze(normed)

    if __name__ == "__main__":
        result = run()
        print(result)


More Examples
=============

Runnable examples live in the ``examples/`` directory of the repository:

- ``examples/global_logging.py`` — logging from outside any ``@nb.fn()`` (the Global loggable).
- ``examples/image_labels.py`` — ``nb.log_image()`` with points, boxes, circles, polygons, and bitmasks.
- ``examples/metrics_gallery.py`` — the five typed metric helpers (`nb.log_line`, `nb.log_bar`, `nb.log_scatter`, `nb.log_pie`, `nb.log_histogram`) plus tag filtering.
- ``examples/basic_pipeline.py`` — minimal starting point.
- ``examples/image_pipeline.py`` — end-to-end image pipeline with decorated edges.

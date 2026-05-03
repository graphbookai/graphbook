.. _API Reference:

API Reference
#############

This is the complete API reference for the ``nebo`` package.


Module: ``nebo``
=================

The top-level module provides all the public functions you need. Import it as:

.. code-block:: python

    import nebo as nb


Decorators
----------

.. function:: nb.fn(func=None, depends_on=None, pausable=False, ui=None)

    Register a function or class for observability. When applied to a function, it sets up scope tracking — the node materializes (becomes visible in the DAG) as soon as the decorated function is executed, regardless of whether it calls a log function. When applied to a class, all methods are wrapped with scope tracking and the class becomes a visual grouping container in the DAG.

    :param func: The function or class to decorate (when used without parentheses).
    :param depends_on: Optional list of decorated functions or node ID strings that this node depends on.
    :param pausable: If True, the function blocks before execution when paused via the web UI.
    :param ui: Optional dict of per-node UI display hints (e.g., ``{"color": "#34d399", "default_tab": "metrics"}``).
    :returns: The decorated function or class (unchanged behavior, with observability added).

    Usage forms:

    .. code-block:: python

        @nb.fn                          # bare decorator
        @nb.fn()                        # with empty parentheses
        @nb.fn(depends_on=[setup])      # with explicit dependencies
        @nb.fn(ui={"color": "#34d399"}) # with per-node UI hints

    **On functions:** The node ID is derived from the function's ``__qualname__``. The function's docstring becomes the node's description. The node materializes (becomes visible) on the first call to the decorated function, so even silent functions that never log appear in the DAG and act as real links in dependency chains.

    **On classes:** All methods are wrapped. The class itself is never a node — it is a transparent bounding box in the DAG. Every method that runs materializes as a node inside that bounding box, including methods that never call a log function.


Logging Functions
-----------------

.. function:: nb.log(message: str | Any, *, step: int | None = None) -> None

    Log a text message to the current node. Tensor-like objects (NumPy arrays, PyTorch tensors) are auto-formatted with shape, dtype, and statistics.

    :param message: The message string or tensor-like object.
    :param step: Optional step counter.

.. function:: nb.log_line(name, value, *, step=None, tags=None)

   Log a scalar line-chart datapoint. Line is the only chart type
   that **accumulates** — repeated calls with the same name append
   another point to the series. ``step`` auto-increments per
   ``(loggable, name)`` when omitted.

   :param name: Metric name.
   :param value: A scalar ``int | float`` (NumPy/PyTorch scalars are accepted).
   :param step: Optional step counter.
   :param tags: List of strings attached to this emission for UI filtering.

.. function:: nb.log_bar(name, value)

   Log a bar-chart snapshot. ``value`` is a dict ``{label: number}``.
   Repeated calls with the same name **overwrite** the prior value.

.. function:: nb.log_pie(name, value)

   Log a pie-chart snapshot. ``value`` is a dict ``{label: number}``.
   Repeated calls with the same name **overwrite** the prior value.

.. function:: nb.log_scatter(name, value, *, colors=False)

   Log a labeled scatter snapshot. ``value`` is a dict
   ``{label: list[(x, y)]}`` — every label becomes its own series on
   the same chart and is toggleable via the UI chip row. Repeated
   calls with the same name **overwrite** the prior value.

   :param colors: When ``True``, distinguish labels by palette color
       (in addition to the per-label shape). Default ``False``
       (every label uses the run color, distinguished by shape only).
       **Not recommended in comparison views** where color is reserved
       for run identity.

.. function:: nb.log_histogram(name, value, *, colors=False)

   Log a labeled histogram snapshot. ``value`` is a dict
   ``{label: list[number]}`` — every label is a distribution; the UI
   bins all labels against a shared range so overlapping
   distributions line up. Repeated calls with the same name
   **overwrite** the prior value. To log a single histogram, wrap in
   a single-key dict, e.g. ``{"all": samples}``.

   :param colors: When ``True``, give each label a distinct palette
       color so overlapping distributions can be picked apart.
       Default ``False`` (every label uses the run color; the overlap
       reads as a single mass via alpha compositing). **Not
       recommended in comparison views** where color is reserved for
       run identity.

The chart type locks on first emission per ``(loggable, name)`` pair —
mixing ``log_line`` and ``log_bar`` for the same metric name raises
``ValueError``.

Steps and tags only apply to ``log_line``. The four snapshot helpers
ignore them; passing ``step=`` or ``tags=`` to ``log_bar`` /
``log_pie`` / ``log_scatter`` / ``log_histogram`` is a ``TypeError``.

Example::

    nb.log_line("loss", 0.5)
    nb.log_bar("counts", {"cat": 3, "dog": 5})
    nb.log_scatter("embed_2d", {"inliers": [(0.1, 0.2), (0.3, 0.4)],
                                 "outliers": [(2.0, -1.0)]})
    nb.log_histogram(
        "latencies",
        {"p50": [...], "p95": [...], "p99": [...]},
        colors=True,
    )
    nb.log_line("lr", 3e-4, tags=["main"])

.. function:: nb.log_image(image, *, name=None, step=None, points=None, boxes=None, circles=None, polygons=None, bitmask=None)

   Log an image with optional geometric labels overlaid.

   :param image: PIL.Image, numpy ndarray, or torch.Tensor.
   :param name: Display label for the image.
   :param step: Optional step counter.
   :param points: Single ``[x, y]`` or list ``[[x, y], ...]``.
   :param boxes: Single ``[x1, y1, x2, y2]`` (xyxy) or a list of them.
   :param circles: Single ``[x, y, r]`` or a list of them.
   :param polygons: Single polygon ``[[x, y], ...]`` or a list of polygons.
   :param bitmask: 2D mask (HxW), 3D stack (NxHxW), or a list of 2D masks.

   Tensors and ndarrays are normalized to plain Python lists; bitmasks are
   PNG-encoded and transmitted inline. The UI's Settings pane > "Image
   labels" section exposes per-(loggable, image, key) visibility and
   opacity controls.

   Example::

       nb.log_image(
           img, name="pred",
           boxes=[[10, 10, 50, 50]],
           points=[[30, 30]],
       )

.. function:: nb.log_audio(audio: Any, sr: int = 16000, *, name: str | None = None, step: int | None = None) -> None

    Log audio data.

    :param audio: Audio data as a NumPy array.
    :param sr: Sample rate (default: 16000).
    :param name: Optional audio clip name.
    :param step: Optional step counter.

.. function:: nb.log_cfg(cfg: dict[str, Any]) -> None

    Log configuration for the current node. Merges *cfg* into the node's ``params`` dict so the Info tab displays all configuration in one place.

    :param cfg: A flat or nested dictionary of configuration values. Only JSON-serializable values are retained.

    Multiple calls within the same node merge dictionaries (later calls win on key conflicts).


Progress Tracking
-----------------

.. function:: nb.track(iterable: Iterable[T], name: str | None = None, total: int | None = None) -> TrackedIterable[T]

    Wrap an iterable for tqdm-like progress tracking. The progress is reported to the terminal dashboard, daemon, and web UI.

    :param iterable: The iterable to wrap.
    :param name: Display name for the progress bar.
    :param total: Total number of items. Auto-detected from ``__len__`` if available.
    :returns: A ``TrackedIterable`` that yields items and reports progress.


Workflow Description
--------------------

.. function:: nb.md(description: str) -> None

    Set or append to the workflow-level Markdown description. Distinct from node docstrings — this describes the overall workflow.

    :param description: Markdown description text.


UI Configuration
-----------------

.. function:: nb.ui(layout: str | None = None, view: str | None = None, minimap: bool | None = None, theme: str | None = None) -> None

    Set run-level UI defaults. These are sent to the daemon and web UI as defaults that the user can override.

    :param layout: DAG layout direction: ``"horizontal"`` or ``"vertical"``.
    :param view: Default view mode: ``"dag"`` or ``"grid"``.
    :param minimap: Whether to show the minimap.
    :param theme: Color theme: ``"dark"`` or ``"light"``.

    Calling ``nb.ui()`` again overwrites the previous defaults.


Initialization
--------------

.. function:: nb.init(port: int = 7861, host: str = "localhost", mode: str = "auto", terminal: bool = True, dag_strategy: str = "object", flush_interval: float = 0.1, store: bool = True) -> None

    Explicitly initialize nebo.

    :param port: Daemon server port (default: 7861).
    :param host: Daemon server host (default: ``"localhost"``).
    :param mode: ``"auto"``, ``"server"``, or ``"local"``.
    :param terminal: Whether to show the Rich terminal display in local mode.
    :param dag_strategy: How DAG edges are inferred: ``"object"`` (default), ``"stack"``, ``"both"``, ``"linear"``, or ``"none"``. ``"linear"`` chains nodes in first-execution order.
    :param flush_interval: Seconds between event flushes (default: 0.1).
    :param store: Whether the daemon should persist this run to a ``.nebo`` file (default: True).

    Mode detection (when ``mode="auto"``):

    1. Check ``NEBO_MODE`` and ``NEBO_SERVER_PORT`` environment variables.
    2. Try connecting to the daemon at ``host:port``.
    3. If found, use server mode. If not, use local mode.

    .. note::

        You rarely need to call ``init()`` explicitly. When using ``nebo run``, the SDK auto-initializes from environment variables on the first ``@fn`` execution.


Human-in-the-Loop
------------------

.. function:: nb.ask(question: str, options: list[str] | None = None, timeout: float | None = None) -> str

    Ask the user a question. In server mode, the question appears in the web UI. In local mode, falls back to a Rich terminal prompt.

    :param question: The question to ask.
    :param options: Optional list of valid response choices.
    :param timeout: Optional timeout in seconds.
    :returns: The user's response string.


State Access
------------

.. function:: nb.get_state() -> SessionState

    Get the global session state singleton. Advanced usage — most users won't need this.

    :returns: The ``SessionState`` instance containing all nodes, edges, and configuration.


CLI Reference: ``nebo``
======================

.. code-block:: text

    nebo <command> [options]

Commands
--------

``serve``
    Start the persistent daemon server.

    .. code-block:: console

        $ nebo serve [--host HOST] [--port PORT] [-d] [--no-store]

    ``--host``
        Host to bind (default: ``localhost``).

    ``--port``
        Port to bind (default: ``7861``).

    ``-d``, ``--daemon``
        Run in background (daemon mode).

    ``--no-store``
        Disable ``.nebo`` file storage globally.

``run``
    Run a pipeline script managed by the daemon.

    .. code-block:: console

        $ nebo run <script> [--name NAME] [--port PORT] [--flush-interval SECS] [args...]

    ``<script>``
        Path to the Python script.

    ``--name``
        Run name/ID (auto-generated if not provided).

``status``
    Show daemon status and recent runs.

    .. code-block:: console

        $ nebo status [--port PORT]

``stop``
    Stop the daemon.

    .. code-block:: console

        $ nebo stop [--port PORT]

``logs``
    View logs from runs.

    .. code-block:: console

        $ nebo logs [--run RUN_ID] [--node NODE] [--limit N] [--port PORT]

``errors``
    View errors from runs.

    .. code-block:: console

        $ nebo errors [--run RUN_ID] [--port PORT]

``load``
    Load a ``.nebo`` file into the daemon for viewing and Q&A.

    .. code-block:: console

        $ nebo load <file> [--port PORT]

``mcp``
    Print MCP connection config for Claude Code / Claude Desktop.

    .. code-block:: console

        $ nebo mcp

``mcp-stdio``
    Run the MCP stdio bridge (used internally).

    .. code-block:: console

        $ nebo mcp-stdio [--port PORT]


MCP Tools Reference
====================

The following 17 MCP tools are available when the daemon is running.

Observation Tools
-----------------

``nebo_get_graph``
    Get the full DAG structure: nodes (with docstrings, execution counts, group membership), edges, and workflow description.

    :param run_id: Optional run ID. Uses the latest run if omitted.

``nebo_get_node_status``
    Get detailed status for a specific node: execution count, params, docstring, recent logs, errors, and progress.

    :param name: The node name (required).
    :param run_id: Optional run ID.

``nebo_get_logs``
    Get recent log entries, optionally filtered by node and run.

    :param node: Optional node name filter.
    :param run_id: Optional run ID.
    :param limit: Maximum entries (default: 100).

``nebo_get_metrics``
    Get metric time series for a node.

    :param node: The node name (required).
    :param name: Optional specific metric name.

``nebo_get_errors``
    Get all errors with full tracebacks, node context, and parameter values.

    :param run_id: Optional run ID.

``nebo_get_description``
    Get the workflow-level description and all node docstrings.

Action Tools
------------

``nebo_run_pipeline``
    Start a pipeline script. Returns a ``run_id`` for tracking.

    :param script_path: Path to the Python script (required).
    :param args: Script arguments.
    :param name: Optional run name/ID.

``nebo_stop_pipeline``
    Stop a running pipeline by run ID.

    :param run_id: The run ID to stop (required).

``nebo_restart_pipeline``
    Stop and re-run a pipeline with the same script and arguments.

    :param run_id: The run ID to restart (required).

``nebo_get_run_status``
    Get the status of a run: running, completed, crashed, or stopped.

    :param run_id: The run ID (required).

``nebo_get_run_history``
    List all runs with outcomes, timestamps, and error counts.

``nebo_get_source_code``
    Read a pipeline source file.

    :param file_path: Path to the source file (required).

``nebo_write_source_code``
    Write or patch a pipeline source file.

    :param file_path: Path to the source file (required).
    :param content: Full file content (replaces entire file).
    :param patches: List of ``{old, new}`` patches to apply.

``nebo_ask_user``
    Send a question to the user via the web UI.

    :param question: The question to ask (required).
    :param options: Valid response options.

``nebo_load_file``
    Load a ``.nebo`` log file into the daemon for viewing and Q&A.

    :param filepath: Absolute path to the ``.nebo`` file (required).

``nebo_chat``
    Ask a question about a run. Uses the run's logs, metrics, graph, and errors to generate an answer via Claude Code CLI.

    :param question: The question to ask (required).
    :param run_id: Optional run ID. Uses the active run if omitted.


Environment Variables
======================

These are set automatically by ``nebo run`` and read by the SDK during auto-initialization:

``NEBO_MODE``
    Execution mode: ``"server"`` or ``"local"``.

``NEBO_SERVER_PORT``
    The daemon server port.

``NEBO_RUN_ID``
    The current run identifier.

``NEBO_DAEMON_PORT``
    Used internally by the daemon process itself.

``NEBO_NO_STORE``
    When set, disables ``.nebo`` file storage globally. The daemon's
    auto-create and ``run_start`` paths skip opening the file writer.
    Useful for ephemeral test daemons and embedders that don't want
    runs persisted to disk.

``NEBO_NO_TERMINAL``
    When set, ``nb.init()`` skips the Rich live terminal dashboard even
    if ``terminal=True`` (the default). Mirrors the per-call
    ``terminal=False`` argument as a process-wide override and is the
    recommended way to suppress the dashboard from headless contexts
    (CI, notebooks, subprocess wrappers).

``NEBO_FLUSH_INTERVAL``
    Override the event flush interval (seconds).


.nebo File Format
==================

Nebo persists runs as append-only binary files using MessagePack.

.. code-block:: text

    [Header]
      magic: "nebo" (4 bytes)
      version: u16 big-endian (currently 1)
      metadata_size: u32 big-endian
      metadata: msgpack map {run_id, script_path, started_at, nebo_version, args}

    [Entry]*
      type: u8 (entry type index)
      size: u32 big-endian (payload size in bytes)
      payload: msgpack map (entry-specific data)

Entry types: log (0), metric (1), image (2), audio (3), node_register (4), edge (5), error (6), ask (7), ui_config (8), text (9), progress (10), config (11), description (12), node_executed (13), ask_response (14), run_start (15), run_completed (16), pause_state (17).

Media assets (images, audio) are embedded as raw bytes inside the msgpack payload, avoiding base64 overhead.

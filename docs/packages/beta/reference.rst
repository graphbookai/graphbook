.. _Beta API Reference:

API Reference
#############

This is the complete API reference for the ``graphbook.beta`` package.


Module: ``graphbook.beta``
===========================

The top-level module provides all the public functions you need. Import it as:

.. code-block:: python

    import graphbook.beta as gb


Decorators
----------

.. function:: gb.fn(func=None, depends_on=None)

    Register a function as a DAG node. When one ``@fn``-decorated function calls another, a directed edge is recorded between them.

    :param func: The function to decorate (when used without parentheses).
    :param depends_on: Optional list of decorated functions or node ID strings that this node depends on.
    :returns: The decorated function (unchanged behavior, with observability added).

    Usage forms:

    .. code-block:: python

        @gb.fn           # bare decorator
        @gb.fn()          # with empty parentheses
        @gb.fn(depends_on=[setup])  # with explicit dependencies

    The node ID is derived from the function's ``__qualname__``. The function's docstring becomes the node's description.


Logging Functions
-----------------

.. function:: gb.log(message: str) -> None

    Log a text message to the current node.

    :param message: The message string.

.. function:: gb.log_metric(name: str, value: float, step: int | None = None) -> None

    Log a scalar metric value. If ``step`` is not provided, it auto-increments per metric name within the current node.

    :param name: The metric name (e.g., ``"loss"``, ``"accuracy"``).
    :param value: The scalar value.
    :param step: Optional step counter.

.. function:: gb.log_image(name: str, image: Any, step: int | None = None) -> None

    Log an image. Accepts PIL images, NumPy arrays (HWC or CHW), or PyTorch tensors.

    :param name: The image name/label.
    :param image: The image data.
    :param step: Optional step counter.

.. function:: gb.log_audio(name: str, audio: Any, sr: int = 16000) -> None

    Log audio data.

    :param name: The audio clip name.
    :param audio: Audio data as a NumPy array.
    :param sr: Sample rate (default: 16000).

.. function:: gb.log_text(name: str, text: str) -> None

    Log rich text or Markdown content.

    :param name: The text name/label.
    :param text: The text/Markdown content.

.. function:: gb.log_cfg(cfg: dict[str, Any]) -> None

    Log configuration for the current node. Merges *cfg* into the node's ``params`` dict so the Info tab displays all configuration in one place.

    :param cfg: A flat or nested dictionary of configuration values. Only JSON-serializable values (str, int, float, bool, list, dict) are retained.

    Multiple calls within the same node merge dictionaries (later calls win on key conflicts).

    .. code-block:: python

        @gb.fn()
        def train(lr=0.001, epochs=50):
            gb.log_cfg({"lr": lr, "epochs": epochs})
            ...


Inspection
----------

.. function:: gb.inspect(obj: Any, name: str | None = None) -> dict

    Inspect an object and log its metadata. Does **not** log raw data — only metadata such as shape, dtype, device, min/max/mean, length, columns, etc.

    :param obj: The object to inspect.
    :param name: Optional name for the inspection.
    :returns: Dictionary of metadata about the object.

    Supported metadata extraction:

    - **PyTorch tensors**: ``shape``, ``dtype``, ``device``, ``requires_grad``, ``min``, ``max``, ``mean``
    - **NumPy arrays**: ``shape``, ``dtype``, ``min``, ``max``, ``mean``
    - **pandas DataFrames**: ``columns``, ``dtypes``
    - **Sequences**: ``length`` (anything with ``__len__``)
    - **All objects**: ``type`` (the class name)


Progress Tracking
-----------------

.. function:: gb.track(iterable: Iterable[T], name: str | None = None, total: int | None = None) -> TrackedIterable[T]

    Wrap an iterable for tqdm-like progress tracking. The progress is reported to the terminal dashboard and daemon.

    :param iterable: The iterable to wrap.
    :param name: Display name for the progress bar.
    :param total: Total number of items. Auto-detected from ``__len__`` if available.
    :returns: A ``TrackedIterable`` that yields items and reports progress.


Workflow Description
--------------------

.. function:: gb.md(description: str) -> None

    Set or append to the workflow-level Markdown description. Distinct from node docstrings — this describes the overall workflow.

    :param description: Markdown description text.


Initialization
--------------

.. function:: gb.init(port: int = 2048, host: str = "localhost", mode: str = "auto", backends: list | None = None, terminal: bool = True) -> None

    Explicitly initialize graphbook beta.

    :param port: Daemon server port (default: 2048).
    :param host: Daemon server host (default: ``"localhost"``).
    :param mode: ``"auto"``, ``"server"``, or ``"local"``.
    :param backends: Optional list of ``LoggingBackend`` instances.
    :param terminal: Whether to show the Rich terminal display in local mode.

    Mode detection (when ``mode="auto"``):

    1. Check ``GRAPHBOOK_MODE`` and ``GRAPHBOOK_SERVER_PORT`` environment variables.
    2. Try connecting to the daemon at ``host:port``.
    3. If found, use server mode. If not, use local mode.

    .. note::

        You rarely need to call ``init()`` explicitly. When using ``graphbook-beta run``, the SDK auto-initializes from environment variables on the first ``@fn`` execution.


Human-in-the-Loop
------------------

.. function:: gb.ask(question: str, options: list[str] | None = None, timeout: float | None = None) -> str

    Ask the user a question. In server mode, sends the question via MCP. In local mode, falls back to a Rich terminal prompt.

    :param question: The question to ask.
    :param options: Optional list of valid response choices.
    :param timeout: Optional timeout in seconds.
    :returns: The user's response string.


State Access
------------

.. function:: gb.get_state() -> SessionState

    Get the global session state singleton. Advanced usage — most users won't need this.

    :returns: The ``SessionState`` instance containing all nodes, edges, and backends.


Protocol: ``LoggingBackend``
----------------------------

.. class:: LoggingBackend

    Protocol for custom logging backend extensions. Implement all methods to route events to external systems.

    .. method:: on_log(node: str, message: str, timestamp: float) -> None
    .. method:: on_metric(node: str, name: str, value: float, step: int) -> None
    .. method:: on_image(node: str, name: str, image_bytes: bytes, step: int) -> None
    .. method:: on_audio(node: str, name: str, audio_bytes: bytes, sr: int) -> None
    .. method:: on_node_start(node: str, params: dict) -> None
    .. method:: on_node_end(node: str, duration: float) -> None
    .. method:: flush() -> None
    .. method:: close() -> None


CLI Reference: ``graphbook-beta``
==================================

.. code-block:: text

    graphbook-beta [--port PORT] <command> [options]

Commands
--------

``serve``
    Start the persistent daemon server.

    .. code-block:: console

        $ graphbook-beta serve [--host HOST] [--port PORT] [-d]

    ``--host``
        Host to bind (default: ``localhost``).

    ``--port``
        Port to bind (default: ``2048``).

    ``-d``, ``--daemon``
        Run in background (daemon mode).

``run``
    Run a pipeline script managed by the daemon. Auto-starts the daemon if not running.

    .. code-block:: console

        $ graphbook-beta run <script> [--name NAME] [--port PORT] [args...]

    ``<script>``
        Path to the Python script.

    ``--name``
        Run name/ID (auto-generated if not provided).

``status``
    Show daemon status and recent runs.

    .. code-block:: console

        $ graphbook-beta status [--port PORT]

``stop``
    Stop the daemon.

    .. code-block:: console

        $ graphbook-beta stop [--port PORT]

``logs``
    View logs from runs.

    .. code-block:: console

        $ graphbook-beta logs [--run RUN_ID] [--node NODE] [--limit N] [--port PORT]

``errors``
    View errors from runs.

    .. code-block:: console

        $ graphbook-beta errors [--run RUN_ID] [--port PORT]

``mcp``
    Print MCP connection config for Claude Code / Claude Desktop.

    .. code-block:: console

        $ graphbook-beta mcp


MCP Tools Reference
====================

The following MCP tools are available when the daemon is running. Each tool communicates with the daemon via HTTP.

Observation Tools
-----------------

``graphbook_get_graph``
    Get the full DAG structure of the running pipeline: nodes (with docstrings, source/non-source status, execution counts), edges, and workflow description.

    :param run_id: Optional run ID. Uses the latest run if omitted.

``graphbook_get_node_status``
    Get detailed status for a specific node: execution count, params, docstring, recent logs, errors, progress, and inspections.

    :param name: The node name (required).
    :param run_id: Optional run ID.

``graphbook_get_logs``
    Get recent log entries, optionally filtered by node and run.

    :param node: Optional node name filter.
    :param run_id: Optional run ID.
    :param limit: Maximum entries (default: 100).

``graphbook_get_metrics``
    Get metric time series for a node.

    :param node: The node name (required).
    :param name: Optional specific metric name.

``graphbook_get_errors``
    Get all errors with full tracebacks, node context, and parameter values.

    :param run_id: Optional run ID.

``graphbook_get_description``
    Get the workflow-level description and all node docstrings.

``graphbook_inspect_object``
    Get the last inspection result for a named object (shape, dtype, etc.).

    :param name: The inspection name (required).
    :param node: Optional node to search in.

Action Tools
------------

``graphbook_run_pipeline``
    Start a pipeline script. Returns a ``run_id`` for tracking.

    :param script_path: Path to the Python script (required).
    :param args: Script arguments.
    :param name: Optional run name/ID.

``graphbook_stop_pipeline``
    Stop a running pipeline by run ID.

    :param run_id: The run ID to stop (required).

``graphbook_restart_pipeline``
    Stop and re-run a pipeline with the same script and arguments.

    :param run_id: The run ID to restart (required).

``graphbook_get_run_status``
    Get the status of a run: running, completed, crashed, or stopped. Includes exit code, duration, and error summary.

    :param run_id: The run ID (required).

``graphbook_get_run_history``
    List all runs with outcomes, timestamps, and error counts.

``graphbook_get_source_code``
    Read a pipeline source file.

    :param file_path: Path to the source file (required).

``graphbook_write_source_code``
    Write or patch a pipeline source file.

    :param file_path: Path to the source file (required).
    :param content: Full file content (replaces entire file).
    :param patches: List of ``{old, new}`` patches to apply.

``graphbook_ask_user``
    Send a question to the user via the terminal dashboard.

    :param question: The question to ask (required).
    :param options: Valid response options.


Environment Variables
======================

These are set automatically by ``graphbook-beta run`` and read by the SDK during auto-initialization:

``GRAPHBOOK_MODE``
    Execution mode: ``"server"`` or ``"local"``.

``GRAPHBOOK_SERVER_PORT``
    The daemon server port.

``GRAPHBOOK_RUN_ID``
    The current run identifier.

``GRAPHBOOK_DAEMON_PORT``
    Used internally by the daemon process itself.

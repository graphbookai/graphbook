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

.. function:: nb.init(port: int = 7861, host: str = "localhost", mode: str = "auto", terminal: bool = True, dag_strategy: str = "object", flush_interval: float = 0.1, store: bool = True, url: str | None = None, api_token: str | None = None) -> None

    Explicitly initialize nebo.

    :param port: Daemon server port (default: 7861).
    :param host: Daemon server host (default: ``"localhost"``).
    :param mode: ``"auto"``, ``"server"``, or ``"local"``.
    :param terminal: Whether to show the Rich terminal display in local mode.
    :param dag_strategy: How DAG edges are inferred: ``"object"`` (default), ``"stack"``, ``"both"``, ``"linear"``, or ``"none"``. ``"linear"`` chains nodes in first-execution order.
    :param flush_interval: Seconds between event flushes (default: 0.1).
    :param store: Whether the daemon should persist this run to a ``.nebo`` file (default: True).
    :param url: Full URL of a remote daemon (e.g. a Hugging Face Space at ``https://username-space.hf.space``). Overrides ``host``+``port``. Defaults to env var ``NEBO_URL``.
    :param api_token: Token for daemons that require auth. Sent as the ``X-Nebo-Token`` header. Defaults to env var ``NEBO_API_TOKEN``.

    Mode detection (when ``mode="auto"``):

    1. Check ``NEBO_MODE`` and ``NEBO_SERVER_PORT`` environment variables.
    2. Try connecting to the daemon at ``host:port`` (or ``url`` if set).
    3. If found, use server mode. If not, use local mode.

    .. note::

        You rarely need to call ``init()`` explicitly. When using ``nebo run``, the SDK auto-initializes from environment variables on the first ``@fn`` execution. To target a remote daemon, set ``NEBO_URL`` and ``NEBO_API_TOKEN`` in the environment so the same code works against a local or remote target.


Notebook Embedding
------------------

.. function:: nb.show(*, run=None, node=None, metric=None, image=None, audio=None, logs=False, dag=False, width="100%", height=600)

    Return a Jupyter-renderable iframe of the daemon UI scoped to one
    slice of a run. The slice is determined by which kwargs are set —
    pass nothing to embed the full run dashboard. At most one slice
    kwarg may be set; passing more than one raises ``ValueError``.

    :param run: Run ID to embed. Defaults to the active run.
    :param node: Node ID or function name. With no slice kwarg, shows the node detail; combined with a slice it filters that slice.
    :param metric: ``str`` shows a single metric by name; ``True`` shows the metrics gallery (filtered by ``node`` if set).
    :param image: Same shape as ``metric`` for images.
    :param audio: Same shape as ``metric`` for audio recordings.
    :param logs: ``True`` shows the logs panel (filtered by ``node`` if set).
    :param dag: ``True`` shows the DAG-only view.
    :param width, height: iframe dimensions. Strings (``"100%"``) or ints (px).
    :returns: A handle whose ``_repr_html_`` emits the ``<iframe>``.

    Example::

        nb.show(metric="loss")                # one metric chart
        nb.show(node="train", metric=True)    # gallery of train's metrics
        nb.show(image="hero.png")             # one image
        nb.show(logs=True, node="train")      # logs panel filtered to train

Iframe URL scheme
~~~~~~~~~~~~~~~~~

The dashboard switches into embedded mode whenever a ``?run=…`` query
param is present. The slice is inferred from the other params — there
is no ``view=`` discriminator:

================================  ====================================
URL                               Renders
================================  ====================================
``?run=X``                        Full run dashboard (DAG + timeline)
``?run=X&dag``                    DAG only
``?run=X&node=Y``                 Single node detail
``?run=X&logs``                   Logs panel
``?run=X&metrics``                Metrics gallery
``?run=X&metric=loss``            Single metric
``?run=X&images``                 Image gallery
``?run=X&image=hero.png``         Single image
``?run=X&audios``                 Audio gallery
``?run=X&audio=bell.wav``         Single audio recording
================================  ====================================

Add ``&node=Y`` to any of the slice forms to filter to one node.
Append ``&token=…`` to authenticate with a token-protected daemon —
the dashboard captures it once, persists it in localStorage, and
strips it from the visible URL.


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
                     [--store-dir DIR] [--api-token TOKEN]
                     [--read public|private] [--write public|private]

    ``--host``
        Host to bind (default: ``localhost``).

    ``--port``
        Port to bind (default: ``7861``).

    ``-d``, ``--daemon``
        Run in background (daemon mode).

    ``--no-store``
        Disable ``.nebo`` file storage globally.

    ``--store-dir DIR``
        Directory for ``.nebo`` files (default: ``./.nebo``). Sets
        ``NEBO_STORE_DIR``. Useful when hosting on Hugging Face Spaces
        where the persistent volume mounts at ``/data``.

    ``--api-token TOKEN``
        Require this token on API requests. Sets ``NEBO_API_TOKEN``.
        See ``--read`` / ``--write`` for the modes that activate when
        the token is set.

    ``--read public|private``
        Read-access mode (default: ``public``). Only matters when
        ``--api-token`` is set.

    ``--write public|private``
        Write-access mode (default: ``private``). Only matters when
        ``--api-token`` is set.

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
    Load a ``.nebo`` file into the daemon for viewing and Q&A. With
    ``--url`` (or ``NEBO_URL`` env), the file is read locally and its
    events are replayed to the remote daemon — useful when the daemon
    is on a Hugging Face Space and can't see the user's filesystem.

    .. code-block:: console

        $ nebo load <file> [--port PORT]
        $ nebo load <file> --url URL [--api-token TOKEN]

    ``--url URL``
        Remote daemon URL (e.g. an HF Space). Defaults to ``NEBO_URL``.

    ``--api-token TOKEN``
        Token for the remote daemon. Defaults to ``NEBO_API_TOKEN``.

``mcp``
    Print MCP connection config for Claude Code / Claude Desktop.

    .. code-block:: console

        $ nebo mcp

``mcp-stdio``
    Run the MCP stdio bridge (used internally).

    .. code-block:: console

        $ nebo mcp-stdio [--port PORT]

``deploy``
    Deploy the nebo daemon to a Hugging Face Space. Creates (or
    reuses) a Docker-SDK Space, sets ``NEBO_API_TOKEN`` as a Space
    secret, sets the read/write mode variables, and uploads a
    Dockerfile and a Spaces-flavored README.

    Requires the optional ``deploy`` extra:

    .. code-block:: console

        $ pip install 'nebo[deploy]'

    .. code-block:: console

        $ nebo deploy --space-id <user>/<space> [--from-source]
                      [--api-token TOKEN] [--hf-token TOKEN] [--private]
                      [--read public|private] [--write public|private]

    ``--space-id <user>/<space>``
        Hugging Face Space identifier (required).

    ``--from-source``
        Build a wheel from the current checkout and ship it instead of
        installing from PyPI. Use this to deploy un-released code.

    ``--api-token TOKEN``
        Token clients must send via ``X-Nebo-Token`` / ``?token=``.
        Random if omitted; printed once after the deploy completes.

    ``--hf-token TOKEN``
        Hugging Face write token. Defaults to the ``HF_TOKEN`` env or
        a cached login (``huggingface-cli login``).

    ``--private``
        Create the Space as HF-private (visible only to your account).

    ``--read public|private`` (default ``public``)
        Read-access mode for the deployed daemon.

    ``--write public|private`` (default ``private``)
        Write-access mode for the deployed daemon.


MCP Tools Reference
====================

The daemon exposes 21 MCP tools split across observation, action, and
write categories.

Observation Tools
-----------------

``nebo_get_graph``
    Get the full DAG structure: nodes (with docstrings, execution counts, group membership), edges, and workflow description.

    :param run_id: Optional run ID. Uses the latest run if omitted.

``nebo_get_loggable_status``
    Get detailed status for a specific loggable (node or global): execution count, params, docstring, recent logs, errors, and progress.

    :param loggable_id: The loggable ID (required).
    :param run_id: Optional run ID.

``nebo_get_logs``
    Get recent log entries, optionally filtered by loggable and run.

    :param loggable_id: Optional loggable ID filter.
    :param run_id: Optional run ID.
    :param limit: Maximum entries (default: 100).

``nebo_get_metrics``
    Get metric time series for a loggable.

    :param loggable_id: The loggable ID (required).
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
    Includes ``metrics_index`` (``{loggable_id: [name, ...]}``) so
    callers can discover available metric names without iterating
    every loggable card.

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

``nebo_wait_for_event``
    Block until a pipeline event occurs or the timeout elapses.

    :param timeout: Max seconds to wait (default: 300).
    :param events: Event types to wait for (default: ``error``, ``completed``, ``ask_prompt``).
    :param run_id: Optional run ID. Uses the latest run if omitted.

``nebo_ask_user``
    Send a question to the user via the terminal dashboard.

    :param question: The question to ask (required).
    :param options: Valid response options.

``nebo_load_file``
    Load a ``.nebo`` log file into the daemon for viewing and Q&A.

    :param filepath: Absolute path to the ``.nebo`` file (required).

``nebo_chat``
    Ask a question about a run. Uses the run's logs, metrics, graph, and errors to generate an answer via Claude Code CLI.

    :param question: The question to ask (required).
    :param run_id: Optional run ID. Uses the active run if omitted.

Write Tools
-----------

These mirror the SDK's ``nb.log_*`` helpers as MCP tools so an
external agent can push data into a run without owning the SDK
process. Each tool accepts a single entry or a list of entries;
entries are auto-registered as loggables so unknown ``loggable_id``
values aren't silently dropped.

``nebo_log_metric``
    Log one or more metric points. Mirrors ``nb.log_line`` /
    ``log_bar`` / ``log_pie`` / ``log_scatter`` / ``log_histogram``.

    :param entries: Single dict or list. Each: ``{run_id?, loggable_id, name, value, type?, step?, tags?}``. Default ``type`` is ``"line"``.
    :param run_id: Default run ID for entries that don't specify one.

``nebo_log_image``
    Log one or more images. Mirrors ``nb.log_image``. Each entry
    supplies either ``url`` (fetched server-side, persisted) or
    ``data`` (already-base64 bytes). Bytes are stored on the daemon so
    the run survives the source URL going stale.

    :param entries: Single dict or list. Each: ``{run_id?, loggable_id, name, url? | data?, step?, labels?}``.
    :param run_id: Default run ID.

``nebo_log_audio``
    Log one or more audio recordings. Same shape as ``nebo_log_image``
    plus an optional per-entry ``sr`` (sample rate, default 16000).

    :param entries: Single dict or list. Each: ``{run_id?, loggable_id, name, url? | data?, sr?, step?}``.
    :param run_id: Default run ID.

``nebo_log_text``
    Log one or more text entries. Mirrors ``nb.log``. ``loggable_id``
    defaults to ``"__global__"`` when omitted.

    :param entries: Single dict or list. Each: ``{run_id?, loggable_id?, message, level?, step?}``.
    :param run_id: Default run ID.


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

SDK-side (read by ``nb.init()``):

``NEBO_URL``
    Full URL of a remote daemon (e.g. ``https://username-space.hf.space``).
    Overrides ``host``+``port`` so the same SDK code targets either a
    local or remote daemon depending on the environment.

``NEBO_API_TOKEN``
    Token sent on every request as the ``X-Nebo-Token`` header.
    Required when the target daemon enforces auth.

Daemon-side (read by ``nebo serve`` / the deployed Space):

``NEBO_API_TOKEN``
    When set, gates the API per the read/write modes below. Routes
    accept the token via ``X-Nebo-Token`` header or ``?token=…`` query
    parameter (the query form is for browser/iframe flows that can't
    set custom WebSocket headers). ``/health`` and the static UI
    bundle stay open in every mode.

``NEBO_READ_MODE``
    ``public`` (default) or ``private``. Gates GET requests when
    ``NEBO_API_TOKEN`` is set. The WebSocket handshake follows this
    mode.

``NEBO_WRITE_MODE``
    ``public`` or ``private`` (default). Gates non-GET requests when
    ``NEBO_API_TOKEN`` is set. Inbound WebSocket events follow this
    mode (unauthed events are silently dropped while the subscription
    stays open).

``NEBO_STORE_DIR``
    Directory the daemon writes ``.nebo`` files into (default:
    ``./.nebo``). Set to a persistent path (e.g. ``/data`` on Hugging
    Face Spaces) so runs survive container restarts.


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

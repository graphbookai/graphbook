"""Graphbook Beta — Lightweight observability for Python programs.

Usage:
    import graphbook.beta as gb

    @gb.fn()
    def my_function():
        gb.log("hello")
        gb.log_metric("loss", 0.5)
"""

from __future__ import annotations

import os
import threading
import time
import uuid
import logging as _stdlib_logging
from typing import Any, Literal, Optional, TypeVar

from graphbook.beta.core.decorators import fn
from graphbook.beta.core.tracker import track
from graphbook.beta.core.config import log_cfg
from graphbook.beta.core.state import _current_node, get_state, LoggingBackend
from graphbook.beta.logging.logger import (
    log,
    log_metric,
    log_image,
    log_audio,
    log_text,
    md,
)

T = TypeVar("T")

_auto_init_done = False
_pause_poll_thread: Optional[threading.Thread] = None
logger = _stdlib_logging.getLogger(__name__)

def _start_pause_poll() -> None:
    """Start a background thread that polls the daemon for pause state changes."""
    global _pause_poll_thread
    state = get_state()
    if not state._has_pausable or state._client is None:
        return
    if _pause_poll_thread is not None and _pause_poll_thread.is_alive():
        return

    def _poll_loop() -> None:
        client = state._client
        while client is not None and client.is_connected():
            try:
                paused = client.get_pause_state()
                state.set_paused(paused)
            except Exception:
                pass
            time.sleep(0.5)

    _pause_poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    _pause_poll_thread.start()


def _ensure_init() -> None:
    """Lazily auto-initialize on first gb.* call.

    Called by the @fn decorator wrapper and logging functions on first
    execution. If the user already called gb.init(), this is a no-op.
    """
    global _auto_init_done
    if _auto_init_done:
        return

    state = get_state()
    # If user already called init() and connected, skip
    if state._mode != "local" or state._client is not None:
        _auto_init_done = True
        return

    # Auto-connect to daemon. Env vars from `graphbook-beta run`
    # take priority if present.
    init(mode="auto", _internal=True)


def init(
    port: int = 2048,
    host: str = "localhost",
    mode: Literal["auto", "server", "local"] = "auto",
    backends: Optional[list[Any]] = None,
    terminal: bool = True,
    dag_strategy: Literal["object", "stack", "both", "none"] = "object",
    flush_interval: float = 0.1,
    _internal: bool = False,
) -> None:
    """Initialize graphbook beta.

    Mode detection (when mode='auto'):
    1. Check environment variables (set by 'graphbook run')
    2. Check for daemon at host:port
    3. If found -> server mode (stream events to daemon)
    4. If not found -> local mode (in-process rich terminal only)

    Args:
        port: Daemon server port (default 2048).
        host: Daemon server host (default localhost).
        mode: 'auto', 'server', or 'local'.
        backends: Optional list of LoggingBackend instances.
        terminal: Whether to show Rich terminal display in local mode.
        dag_strategy: How DAG edges are inferred between steps.
            'object' (default) uses sibling data-flow edges with parent
            fallback. 'stack' uses caller-to-callee edges only. 'both'
            is the union of object and stack edges.
        flush_interval: Seconds between event flushes (default 0.1).
    """
    global _auto_init_done

    # If already initialized, warn and no-op (unless called internally by _ensure_init)
    if _auto_init_done and not _internal:
        import warnings
        warnings.warn(
            "graphbook was already implicitly initialized by a prior gb.* call. "
            "Call gb.init() before any @gb.fn() execution, gb.log(), gb.md(), etc. "
            "This gb.init() call will be ignored.",
            stacklevel=2,
        )
        return

    _auto_init_done = True
    state = get_state()
    state.port = port
    state.dag_strategy = dag_strategy

    if backends:
        state.backends.extend(backends)

    # Check environment overrides (set by `graphbook run`)
    env_mode = os.environ.get("GRAPHBOOK_MODE")
    env_port = os.environ.get("GRAPHBOOK_SERVER_PORT")
    env_run_id = os.environ.get("GRAPHBOOK_RUN_ID")

    env_flush_interval = os.environ.get("GRAPHBOOK_FLUSH_INTERVAL")

    if env_port:
        port = int(env_port)
        state.port = port
    if env_mode:
        mode = env_mode  # type: ignore
    if env_flush_interval:
        flush_interval = float(env_flush_interval)

    resolved_mode = mode

    # Generate a run_id if not provided by env (e.g. direct script execution)
    run_id = env_run_id
    script_name: Optional[str] = None
    if not run_id and resolved_mode != "local":
        import sys
        script_name = os.path.basename(sys.argv[0]) if sys.argv else "script"
        run_id = f"{uuid.uuid4().hex[:12]}"

    if resolved_mode == "auto":
        # Try to connect to daemon
        try:
            from graphbook.beta.core.client import DaemonClient
            client = DaemonClient(host=host, port=port, run_id=run_id, flush_interval=flush_interval)
            if client.connect():
                resolved_mode = "server"
                state._client = client
            else:
                resolved_mode = "local"
        except Exception:
            resolved_mode = "local"
    elif resolved_mode == "server":
        from graphbook.beta.core.client import DaemonClient
        client = DaemonClient(host=host, port=port, run_id=run_id, flush_interval=flush_interval)
        if not client.connect():
            print(f"Warning: Could not connect to graphbook daemon at {host}:{port}. Falling back to local mode.")
            resolved_mode = "local"
        else:
            state._client = client

    # Send run_start event so the daemon knows the script name
    if state._client is not None and script_name:
        state._send_to_client({
            "type": "run_start",
            "data": {"script_path": script_name},
        })

    state._mode = resolved_mode

    if terminal:
        try:
            from graphbook.beta.terminal.display import TerminalDisplay
            import atexit
            if state._display is None:
                state._display = TerminalDisplay()
                atexit.register(state._display.stop)
        except ImportError:
            pass

    # Start pause polling if we have pausable nodes and are in server mode
    if state._client is not None:
        _start_pause_poll()


def ask(
    question: str,
    options: Optional[list[str]] = None,
    timeout: Optional[float] = None,
) -> str:
    """Ask a question via the web UI or terminal fallback.

    In server mode, sends an ask_prompt event to the daemon and polls
    for a response from the web UI.  In local mode, falls back to a
    Rich terminal prompt.

    Args:
        question: The question to ask.
        options: Optional list of valid responses.
        timeout: Optional timeout in seconds.

    Returns:
        The response string.

    Raises:
        TimeoutError: If timeout expires with no response (server mode only).
    """
    state = get_state()
    client = getattr(state, "_client", None)

    # Server mode: send event and poll for web UI response
    if client and client.is_connected():
        ask_id = str(uuid.uuid4())
        node_name = _current_node.get() or ""
        run_id = getattr(client, "_run_id", None) or ""

        client.send_event({
            "type": "ask_prompt",
            "ask_id": ask_id,
            "node": node_name,
            "node_name": node_name,
            "question": question,
            "options": options,
            "timeout_seconds": timeout,
        })
        client.flush()

        poll_path = f"/runs/{run_id}/ask/{ask_id}/respond"
        poll_interval = 0.5
        deadline = time.monotonic() + timeout if timeout else None

        while True:
            if deadline and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"No response to ask '{question}' within {timeout}s"
                )
            time.sleep(poll_interval)
            resp = client.get(poll_path)
            if resp and resp.get("status") == "answered":
                return resp["response"]

    # Local mode: terminal fallback
    display = getattr(state, "_display", None)
    if display is not None:
        display.pause()

    try:
        from rich.prompt import Prompt
        if options:
            return Prompt.ask(question, choices=options)
        return Prompt.ask(question)
    except (ImportError, EOFError):
        if options:
            return options[0]
        return ""
    finally:
        if display is not None:
            display.resume()


__all__ = [
    "fn",
    "track",
    "log_cfg",
    "init",
    "log",
    "log_metric",
    "log_image",
    "log_audio",
    "log_text",
    "md",
    "ask",
    "get_state",
    "LoggingBackend",
]

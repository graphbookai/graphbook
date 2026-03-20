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
logger = _stdlib_logging.getLogger(__name__)

def _ensure_init() -> None:
    """Lazily auto-initialize when GRAPHBOOK_MODE env vars are detected.

    Called by the @fn decorator wrapper on first execution. If the user
    already called gb.init(), this is a no-op.
    """
    global _auto_init_done
    if _auto_init_done:
        return
    _auto_init_done = True

    state = get_state()
    # If user already called init() and connected, skip
    if state._mode != "local" or state._client is not None:
        return

    # Always try to connect to the daemon (auto mode).
    # Env vars from `graphbook-beta run` take priority if present.
    init(mode="auto")

    # Replay pre-init state (nodes registered at import, md() calls, etc.)
    if state._client is not None:
        if state.workflow_description:
            state._send_to_client({
                "type": "description",
                "data": {"description": state.workflow_description},
            })
        for nid, node in state.nodes.items():
            state._send_to_client({
                "type": "node_register",
                "node": nid,
                "data": {
                    "node_id": nid,
                    "func_name": node.func_name,
                    "docstring": node.docstring,
                },
            })


def init(
    port: int = 2048,
    host: str = "localhost",
    mode: Literal["auto", "server", "local"] = "auto",
    backends: Optional[list[Any]] = None,
    terminal: bool = True,
    dag_strategy: Literal["object", "stack", "both", "none"] = "object",
    flush_interval: float = 0.1,
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

    if resolved_mode == "local" and terminal:
        try:
            from graphbook.beta.terminal.display import TerminalDisplay
            if state._display is None:
                state._display = TerminalDisplay()
        except ImportError:
            pass


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

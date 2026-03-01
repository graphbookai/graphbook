"""Graphbook Beta — Lightweight observability for Python programs.

Usage:
    import graphbook.beta as gb

    @gb.step()
    def my_function():
        gb.log("hello")
        gb.log_metric("loss", 0.5)
"""

from __future__ import annotations

import os
from typing import Any, Literal, Optional, TypeVar

from hydr8 import override

from graphbook.beta.core.decorators import step
from graphbook.beta.core.tracker import track
from graphbook.beta.core.config import configure
from graphbook.beta.core.state import get_state, LoggingBackend
from graphbook.beta.logging.logger import (
    log,
    log_metric,
    log_image,
    log_audio,
    log_text,
    inspect,
    md,
)

T = TypeVar("T")

_auto_init_done = False


def _ensure_init() -> None:
    """Lazily auto-initialize when GRAPHBOOK_MODE env vars are detected.

    Called by the @step decorator wrapper on first execution. If the user
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

    env_mode = os.environ.get("GRAPHBOOK_MODE")
    env_port = os.environ.get("GRAPHBOOK_SERVER_PORT")
    if env_mode or env_port:
        # Auto-init with env-detected settings
        init(mode="auto")

        # Replay pre-init state (nodes registered at import, md() calls, etc.)
        if state._client is not None:
            # Replay workflow description
            if state.workflow_description:
                state._send_to_client({
                    "type": "description",
                    "data": {"description": state.workflow_description},
                })
            # Replay node registrations
            for nid, node in state.nodes.items():
                state._send_to_client({
                    "type": "node_register",
                    "node": nid,
                    "data": {
                        "node_id": nid,
                        "func_name": node.func_name,
                        "docstring": node.docstring,
                        "config_key": node.config_key,
                    },
                })


def init(
    port: int = 2048,
    host: str = "localhost",
    mode: Literal["auto", "server", "local"] = "auto",
    backends: Optional[list[Any]] = None,
    terminal: bool = True,
) -> None:
    """Initialize graphbook beta.

    Mode detection (when mode='auto'):
    1. Check environment variables (set by 'graphbook run')
    2. Check for daemon at host:port
    3. If found → server mode (stream events to daemon)
    4. If not found → local mode (in-process rich terminal only)

    Args:
        port: Daemon server port (default 2048).
        host: Daemon server host (default localhost).
        mode: 'auto', 'server', or 'local'.
        backends: Optional list of LoggingBackend instances.
        terminal: Whether to show Rich terminal display in local mode.
    """
    state = get_state()
    state.port = port

    if backends:
        state.backends.extend(backends)

    # Check environment overrides (set by `graphbook run`)
    env_mode = os.environ.get("GRAPHBOOK_MODE")
    env_port = os.environ.get("GRAPHBOOK_SERVER_PORT")
    env_run_id = os.environ.get("GRAPHBOOK_RUN_ID")

    if env_port:
        port = int(env_port)
        state.port = port
    if env_mode:
        mode = env_mode  # type: ignore

    resolved_mode = mode

    if resolved_mode == "auto":
        # Try to connect to daemon
        try:
            from graphbook.beta.core.client import DaemonClient
            client = DaemonClient(host=host, port=port, run_id=env_run_id)
            if client.connect():
                resolved_mode = "server"
                state._client = client
            else:
                resolved_mode = "local"
        except Exception:
            resolved_mode = "local"
    elif resolved_mode == "server":
        from graphbook.beta.core.client import DaemonClient
        client = DaemonClient(host=host, port=port, run_id=env_run_id)
        if not client.connect():
            print(f"Warning: Could not connect to graphbook daemon at {host}:{port}. Falling back to local mode.")
            resolved_mode = "local"
        else:
            state._client = client

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
    """Ask a question via MCP or terminal fallback.

    Args:
        question: The question to ask.
        options: Optional list of valid responses.
        timeout: Optional timeout in seconds.

    Returns:
        The response string.
    """
    state = get_state()

    # In server mode, send ask event to daemon
    if hasattr(state, '_client') and state._client and state._client.is_connected():
        state._client.send_event({
            "type": "ask",
            "question": question,
            "options": options,
        })

    # Pause the live display so it doesn't overwrite the prompt
    display = state._display
    if display is not None:
        display.pause()

    # Fallback to terminal
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
    "step",
    "track",
    "configure",
    "override",
    "init",
    "log",
    "log_metric",
    "log_image",
    "log_audio",
    "log_text",
    "inspect",
    "md",
    "ask",
    "get_state",
    "LoggingBackend",
]

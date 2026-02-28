"""Graphbook Beta — Lightweight observability for Python programs.

Usage:
    import graphbook.beta as gb

    @gb.step()
    def my_function():
        gb.log("hello")
        gb.log_metric("loss", 0.5)
"""

from __future__ import annotations

from typing import Any, Optional, TypeVar

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


def init(
    port: int = 2048,
    backends: Optional[list[Any]] = None,
    terminal: bool = True,
    server: bool = True,
) -> None:
    """Initialize graphbook beta.

    This is optional — graphbook auto-initializes on first @step registration.
    Call this explicitly to configure port, backends, or disable features.

    Args:
        port: Port for the local server (default 2048).
        backends: Optional list of LoggingBackend instances.
        terminal: Whether to show the Rich terminal display.
        server: Whether to auto-start the server.
    """
    state = get_state()
    state.port = port

    if backends:
        state.backends.extend(backends)

    if terminal:
        state.ensure_display()

    if server:
        try:
            from graphbook.beta.server.manager import ensure_server
            ensure_server(port=port)
        except Exception:
            pass


def ask(
    question: str,
    options: Optional[list[str]] = None,
    timeout: Optional[float] = None,
) -> str:
    """Ask a question via MCP or terminal fallback.

    Pauses execution until a response is received.

    Args:
        question: The question to ask.
        options: Optional list of valid responses.
        timeout: Optional timeout in seconds.

    Returns:
        The response string.
    """
    # Try MCP first
    state = get_state()
    if state._queue is not None:
        try:
            state._queue.put_event({
                "type": "ask",
                "question": question,
                "options": options,
            })
        except Exception:
            pass

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
    except EOFError:
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

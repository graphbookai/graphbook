"""Async log queue with background flush."""

from __future__ import annotations

import atexit
import queue
import threading
import time
from typing import Any, Callable, Optional


class LogQueue:
    """Thread-safe log queue with batched background flushing."""

    def __init__(
        self,
        flush_callback: Optional[Callable[[list[dict]], None]] = None,
        flush_interval: float = 0.1,
    ) -> None:
        """Initialize the log queue.

        Args:
            flush_callback: Function called with batched events.
            flush_interval: Seconds between flushes.
        """
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._flush_callback = flush_callback
        self._flush_interval = flush_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._events_buffer: list[dict] = []

    def start(self) -> None:
        """Start the background flush thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
        atexit.register(self.stop)

    def stop(self) -> None:
        """Stop the flush thread and flush remaining events."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._flush_remaining()

    def put_event(self, event: dict[str, Any]) -> None:
        """Add an event to the queue."""
        self._queue.put(event)

    def _flush_loop(self) -> None:
        """Background loop that batches and flushes events."""
        last_flush = time.monotonic()

        while self._running:
            try:
                event = self._queue.get(timeout=self._flush_interval)
                self._events_buffer.append(event)
            except queue.Empty:
                pass

            now = time.monotonic()

            if (now - last_flush) >= self._flush_interval and self._events_buffer:
                self._do_flush()
                last_flush = now

    def _flush_remaining(self) -> None:
        """Flush all remaining events synchronously."""
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                self._events_buffer.append(event)
            except queue.Empty:
                break

        if self._events_buffer:
            self._do_flush()

    def _do_flush(self) -> None:
        """Execute the flush callback with buffered events."""
        if not self._events_buffer:
            return
        batch = self._events_buffer[:]
        self._events_buffer.clear()

        if self._flush_callback:
            try:
                self._flush_callback(batch)
            except Exception:
                pass

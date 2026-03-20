"""Tests for the async log queue."""

from __future__ import annotations

import time
import pytest

from graphbook.beta.logging.queue import LogQueue


class TestLogQueue:
    """Tests for the LogQueue."""

    def test_queue_collects_events(self) -> None:
        """Queue should collect events and flush them."""
        flushed = []

        def on_flush(batch):
            flushed.extend(batch)

        q = LogQueue(flush_callback=on_flush, flush_interval=0.05)
        q.start()

        for i in range(10):
            q.put_event({"type": "log", "message": f"msg {i}"})

        time.sleep(0.3)
        q.stop()

        assert len(flushed) == 10

    def test_queue_flushes_on_stop(self) -> None:
        """Remaining events should flush on stop."""
        flushed = []

        def on_flush(batch):
            flushed.extend(batch)

        q = LogQueue(flush_callback=on_flush, flush_interval=10.0)
        q.start()

        q.put_event({"type": "log", "message": "last msg"})
        time.sleep(0.05)
        q.stop()

        assert len(flushed) >= 1

    def test_queue_handles_no_callback(self) -> None:
        """Queue without a callback should not crash."""
        q = LogQueue(flush_callback=None)
        q.start()
        q.put_event({"type": "test"})
        time.sleep(0.2)
        q.stop()

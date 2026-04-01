"""Tests for the DaemonClient."""

from __future__ import annotations

import time

import pytest

from graphbook.beta.core.client import DaemonClient


class TestDaemonClient:
    """Tests for the SDK daemon client."""

    def test_init_defaults(self) -> None:
        """Should initialize with default host/port."""
        client = DaemonClient()
        assert client._host == "localhost"
        assert client._port == 2048
        assert client._connected is False

    def test_connect_fails_when_no_server(self) -> None:
        """Should return False when daemon is not running."""
        client = DaemonClient(port=19999)  # unlikely to be running
        assert client.connect() is False
        assert client.is_connected() is False

    def test_send_event_buffers_when_disconnected(self) -> None:
        """Should buffer events in fallback buffer when not connected."""
        client = DaemonClient(port=19999)
        client.send_event({"type": "log", "message": "buffered"})
        assert len(client._fallback_buffer) == 1
        assert client._fallback_buffer[0]["message"] == "buffered"

    def test_send_events_multiple(self) -> None:
        """Should buffer multiple events."""
        client = DaemonClient(port=19999)
        client.send_events([
            {"type": "log", "message": "a"},
            {"type": "log", "message": "b"},
        ])
        assert len(client._fallback_buffer) == 2

    def test_disconnect_safe_when_not_connected(self) -> None:
        """Should not crash when disconnecting without connection."""
        client = DaemonClient(port=19999)
        client.disconnect()  # should not raise


class TestModeDetection:
    """Tests for mode detection in gb.init()."""

    def setup_method(self) -> None:
        import graphbook.beta as gb
        from graphbook.beta.core.state import SessionState
        SessionState.reset_singleton()
        gb._auto_init_done = False

    def test_local_mode_when_no_daemon(self) -> None:
        """Should fall back to local mode when daemon is not running."""
        import os
        # Clear any environment overrides
        for key in ["GRAPHBOOK_MODE", "GRAPHBOOK_SERVER_PORT", "GRAPHBOOK_RUN_ID"]:
            os.environ.pop(key, None)

        import graphbook.beta as gb
        gb.init(port=19999, mode="auto", terminal=False)

        from graphbook.beta.core.state import get_state
        state = get_state()
        assert state._mode == "local"

    def test_explicit_local_mode(self) -> None:
        """Should use local mode when explicitly set."""
        import graphbook.beta as gb
        gb.init(mode="local", terminal=False)

        from graphbook.beta.core.state import get_state
        state = get_state()
        assert state._mode == "local"

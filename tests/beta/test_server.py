"""Tests for the server protocol and state."""

from __future__ import annotations

import json
import pytest

from graphbook.beta.server.protocol import Message, MessageType, encode_batch, decode_batch


class TestProtocol:
    """Tests for the message protocol."""

    def test_message_to_json(self) -> None:
        """Message should serialize to JSON."""
        msg = Message(type=MessageType.LOG, data={"message": "hello"}, node="my_node")
        raw = msg.to_json()
        parsed = json.loads(raw)
        assert parsed["type"] == "log"
        assert parsed["data"]["message"] == "hello"
        assert parsed["node"] == "my_node"

    def test_message_from_json(self) -> None:
        """Message should deserialize from JSON."""
        raw = json.dumps({
            "type": "metric",
            "data": {"name": "loss", "value": 0.5},
            "timestamp": 1234567890.0,
            "node": "train",
        })
        msg = Message.from_json(raw)
        assert msg.type == MessageType.METRIC
        assert msg.data["value"] == 0.5
        assert msg.node == "train"

    def test_encode_decode_batch(self) -> None:
        """Batch encoding/decoding should round-trip."""
        events = [
            {"type": "log", "message": "hello"},
            {"type": "metric", "name": "loss", "value": 0.1},
        ]
        encoded = encode_batch(events)
        decoded = decode_batch(encoded)
        assert decoded == events

    def test_message_types_enum(self) -> None:
        """All expected message types should be defined."""
        assert MessageType.LOG.value == "log"
        assert MessageType.METRIC.value == "metric"
        assert MessageType.PROGRESS.value == "progress"
        assert MessageType.ERROR.value == "error"
        assert MessageType.ASK.value == "ask_prompt"


class TestDaemonIngest:
    """Tests for the daemon state event ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_log_event(self) -> None:
        """Daemon state should ingest log events."""
        from graphbook.beta.server.daemon import DaemonState

        state = DaemonState()
        state.create_run("test.py", run_id="r1")
        await state.ingest_events([{
            "type": "node_register",
            "data": {"node_id": "my_node", "func_name": "my_func"},
        }], "r1")
        assert "my_node" in state.runs["r1"].nodes

        await state.ingest_events([{
            "type": "log",
            "node": "my_node",
            "message": "test log",
        }], "r1")
        assert len(state.runs["r1"].logs) == 1

    @pytest.mark.asyncio
    async def test_ingest_edge(self) -> None:
        """Daemon state should track edges."""
        from graphbook.beta.server.daemon import DaemonState

        state = DaemonState()
        state.create_run("test.py", run_id="r1")
        await state.ingest_events([
            {"type": "node_register", "data": {"node_id": "a", "func_name": "a"}},
            {"type": "node_register", "data": {"node_id": "b", "func_name": "b"}},
        ], "r1")
        await state.ingest_events([{
            "type": "edge",
            "data": {"source": "a", "target": "b"},
        }], "r1")
        assert len(state.runs["r1"].edges) == 1
        assert state.runs["r1"].nodes["b"].is_source is False

    @pytest.mark.asyncio
    async def test_ingest_error(self) -> None:
        """Daemon state should capture errors."""
        from graphbook.beta.server.daemon import DaemonState

        state = DaemonState()
        state.create_run("test.py", run_id="r1")
        await state.ingest_events([
            {"type": "node_register", "data": {"node_id": "err_node", "func_name": "err"}},
        ], "r1")
        await state.ingest_events([{
            "type": "error",
            "node": "err_node",
            "data": {"error": "something went wrong", "type": "RuntimeError"},
        }], "r1")
        assert len(state.runs["r1"].nodes["err_node"].errors) == 1

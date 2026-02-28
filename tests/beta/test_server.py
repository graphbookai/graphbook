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
        assert MessageType.ASK.value == "ask"


class TestServerState:
    """Tests for the in-memory server state."""

    @pytest.mark.asyncio
    async def test_ingest_log_event(self) -> None:
        """Server state should ingest log events."""
        from graphbook.beta.server.app import ServerState

        state = ServerState()
        # Register a node first
        await state.ingest_batch([{
            "type": "node_register",
            "data": {"node_id": "my_node", "func_name": "my_func"},
        }])
        assert "my_node" in state.nodes

        # Log an event
        await state.ingest_batch([{
            "type": "log",
            "node": "my_node",
            "message": "test log",
        }])
        assert len(state.logs) == 1

    @pytest.mark.asyncio
    async def test_ingest_edge(self) -> None:
        """Server state should track edges."""
        from graphbook.beta.server.app import ServerState

        state = ServerState()
        await state.ingest_batch([
            {"type": "node_register", "data": {"node_id": "a", "func_name": "a"}},
            {"type": "node_register", "data": {"node_id": "b", "func_name": "b"}},
        ])
        await state.ingest_batch([{
            "type": "edge",
            "data": {"source": "a", "target": "b"},
        }])
        assert len(state.edges) == 1
        assert state.nodes["b"]["is_source"] is False

    @pytest.mark.asyncio
    async def test_ingest_error(self) -> None:
        """Server state should capture errors."""
        from graphbook.beta.server.app import ServerState

        state = ServerState()
        await state.ingest_batch([
            {"type": "node_register", "data": {"node_id": "err_node", "func_name": "err"}},
        ])
        await state.ingest_batch([{
            "type": "error",
            "node": "err_node",
            "data": {"error": "something went wrong", "type": "RuntimeError"},
        }])
        assert len(state.nodes["err_node"]["errors"]) == 1

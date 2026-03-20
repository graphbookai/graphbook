"""Client-server message protocol for graphbook beta."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class MessageType(str, Enum):
    """Types of messages in the protocol."""
    LOG = "log"
    METRIC = "metric"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"
    PROGRESS = "progress"
    ERROR = "error"
    NODE_REGISTER = "node_register"
    EDGE = "edge"
    ASK = "ask_prompt"
    ASK_RESPONSE = "ask_response"
    GRAPH_UPDATE = "graph_update"
    HEALTH = "health"
    CONFIG = "config"
    DESCRIPTION = "description"
    PAUSE_STATE = "pause_state"


@dataclass
class Message:
    """A protocol message."""
    type: MessageType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    node: Optional[str] = None

    def to_json(self) -> str:
        d = {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "node": self.node,
        }
        return json.dumps(d, default=str)

    @classmethod
    def from_json(cls, raw: str) -> Message:
        d = json.loads(raw)
        return cls(
            type=MessageType(d["type"]) if d.get("type") in MessageType._value2member_map_ else d.get("type", "log"),
            data=d.get("data", {}),
            timestamp=d.get("timestamp", time.time()),
            node=d.get("node"),
        )


def encode_batch(events: list[dict[str, Any]]) -> str:
    """Encode a batch of events as JSON."""
    return json.dumps(events, default=str)


def decode_batch(raw: str) -> list[dict[str, Any]]:
    """Decode a batch of events from JSON."""
    return json.loads(raw)

"""FastAPI server for graphbook beta."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from graphbook.beta.server.protocol import MessageType, decode_batch


class ServerState:
    """In-memory server state."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, str]] = []
        self._edge_set: set[tuple[str, str]] = set()
        self.logs: list[dict[str, Any]] = []
        self.workflow_description: Optional[str] = None
        self.pending_asks: list[dict[str, Any]] = []
        self.ask_responses: dict[str, str] = {}
        self._ws_clients: list[Any] = []
        self._lock = asyncio.Lock()

    async def ingest_batch(self, events: list[dict[str, Any]]) -> None:
        """Ingest a batch of events."""
        async with self._lock:
            for event in events:
                await self._process_event(event)

        # Broadcast to WebSocket clients
        for ws in self._ws_clients[:]:
            try:
                await ws.send_json({"type": "batch", "events": events})
            except Exception:
                self._ws_clients.remove(ws)

    async def _process_event(self, event: dict[str, Any]) -> None:
        """Process a single event."""
        event_type = event.get("type", "")
        node_id = event.get("node")

        if event_type == "log":
            self.logs.append(event)
            if node_id and node_id in self.nodes:
                if "logs" not in self.nodes[node_id]:
                    self.nodes[node_id]["logs"] = []
                self.nodes[node_id]["logs"].append(event)

        elif event_type == "metric":
            if node_id and node_id in self.nodes:
                name = event.get("name", "")
                value = event.get("value", 0)
                step = event.get("step", 0)
                if "metrics" not in self.nodes[node_id]:
                    self.nodes[node_id]["metrics"] = {}
                if name not in self.nodes[node_id]["metrics"]:
                    self.nodes[node_id]["metrics"][name] = []
                self.nodes[node_id]["metrics"][name].append({"step": step, "value": value})

        elif event_type == "progress":
            if node_id and node_id in self.nodes:
                self.nodes[node_id]["progress"] = event.get("data", {})

        elif event_type == "error":
            error_data = event.get("data", event)
            if node_id and node_id in self.nodes:
                if "errors" not in self.nodes[node_id]:
                    self.nodes[node_id]["errors"] = []
                self.nodes[node_id]["errors"].append(error_data)

        elif event_type == "node_register":
            data = event.get("data", {})
            nid = data.get("node_id", node_id or "")
            if nid and nid not in self.nodes:
                self.nodes[nid] = {
                    "name": nid,
                    "func_name": data.get("func_name", ""),
                    "docstring": data.get("docstring"),
                    "config_key": data.get("config_key"),
                    "exec_count": 0,
                    "is_source": True,
                    "params": {},
                    "logs": [],
                    "metrics": {},
                    "errors": [],
                    "inspections": {},
                    "progress": None,
                }

        elif event_type == "edge":
            data = event.get("data", {})
            src = data.get("source", "")
            tgt = data.get("target", "")
            key = (src, tgt)
            if key not in self._edge_set:
                self._edge_set.add(key)
                self.edges.append({"source": src, "target": tgt})
                if tgt in self.nodes:
                    self.nodes[tgt]["is_source"] = False

        elif event_type == "inspection":
            if node_id and node_id in self.nodes:
                data = event.get("data", {})
                name = data.get("name", "unnamed")
                if "inspections" not in self.nodes[node_id]:
                    self.nodes[node_id]["inspections"] = {}
                self.nodes[node_id]["inspections"][name] = data

        elif event_type == "ask":
            self.pending_asks.append(event)

        elif event_type == "description":
            self.workflow_description = event.get("data", {}).get("description", "")


def create_app() -> Any:
    """Create the FastAPI application."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Graphbook Beta Server")
    state = ServerState()

    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": time.time()}

    @app.post("/ingest")
    async def ingest(events: list[dict[str, Any]]):
        await state.ingest_batch(events)
        return {"status": "ok", "count": len(events)}

    @app.get("/graph")
    async def get_graph():
        return {
            "nodes": state.nodes,
            "edges": state.edges,
            "workflow_description": state.workflow_description,
        }

    @app.get("/nodes/{name}")
    async def get_node(name: str):
        if name in state.nodes:
            return state.nodes[name]
        return JSONResponse(status_code=404, content={"error": f"Node {name} not found"})

    @app.get("/logs")
    async def get_logs(node: Optional[str] = None, limit: int = 100):
        if node:
            logs = [l for l in state.logs if l.get("node") == node]
        else:
            logs = state.logs
        return {"logs": logs[-limit:]}

    @app.get("/errors")
    async def get_errors():
        all_errors = []
        for nid, n in state.nodes.items():
            for err in n.get("errors", []):
                all_errors.append(err)
        return {"errors": all_errors}

    @app.get("/asks")
    async def get_asks():
        return {"pending": state.pending_asks}

    @app.post("/ask_response")
    async def post_ask_response(data: dict):
        ask_id = data.get("id", "")
        response = data.get("response", "")
        state.ask_responses[ask_id] = response
        return {"status": "ok"}

    @app.websocket("/stream")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        state._ws_clients.append(ws)
        try:
            while True:
                data = await ws.receive_text()
                events = decode_batch(data)
                await state.ingest_batch(events)
        except WebSocketDisconnect:
            state._ws_clients.remove(ws)
        except Exception:
            if ws in state._ws_clients:
                state._ws_clients.remove(ws)

    return app

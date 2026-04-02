"""Persistent daemon server for graphbook beta.

The daemon outlives individual pipeline runs, retaining logs, errors, and DAG
state across crashes and restarts. AI agents connect via MCP to the same server.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import WebSocket, WebSocketDisconnect
from graphbook.beta.server.protocol import MessageType, decode_batch


RunStatus = Literal["starting", "running", "completed", "crashed", "stopped"]


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: float
    node: Optional[str]
    message: str
    level: str = "info"
    type: str = "log"
    step: Optional[int] = None
    extra: dict = field(default_factory=dict)


@dataclass
class ErrorEntry:
    """An enriched error entry with full node context."""
    timestamp: float
    node_name: str
    node_docstring: Optional[str]
    exception_type: str
    exception_message: str
    traceback: str
    execution_count: int
    params: dict = field(default_factory=dict)
    last_logs: list[str] = field(default_factory=list)


@dataclass
class NodeState:
    """State for a single DAG node within a run."""
    name: str
    func_name: str
    docstring: Optional[str] = None
    exec_count: int = 0
    is_source: bool = True
    pausable: bool = False
    params: dict = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)
    metrics: dict[str, list] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    audio: list[dict] = field(default_factory=list)
    progress: Optional[dict] = None


@dataclass
class Run:
    """Represents a single pipeline run managed by the daemon."""
    id: str
    script_path: str
    args: list[str] = field(default_factory=list)
    status: RunStatus = "starting"
    process: Any = None  # subprocess.Popen, not serializable
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    nodes: dict[str, NodeState] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)
    _edge_set: set[tuple[str, str]] = field(default_factory=set, repr=False)
    logs: list[LogEntry] = field(default_factory=list)
    errors: list[ErrorEntry] = field(default_factory=list)
    metrics: dict[str, list] = field(default_factory=dict)
    pending_asks: dict[str, dict] = field(default_factory=dict)
    ask_responses: dict[str, str] = field(default_factory=dict)
    source_hash: Optional[str] = None
    workflow_description: Optional[str] = None
    config: dict = field(default_factory=dict)
    paused: bool = False
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    significant_events: list[dict] = field(default_factory=list)

    def get_graph(self) -> dict:
        """Return the DAG as a serializable dict."""
        return {
            "nodes": {
                nid: {
                    "name": n.name,
                    "func_name": n.func_name,
                    "docstring": n.docstring,
                    "exec_count": n.exec_count,
                    "is_source": n.is_source,
                    "pausable": n.pausable,
                    "params": n.params,
                    "progress": n.progress,
                }
                for nid, n in self.nodes.items()
            },
            "edges": self.edges,
            "workflow_description": self.workflow_description,
            "has_pausable": any(n.pausable for n in self.nodes.values()),
            "paused": self.paused,
        }

    def get_summary(self) -> dict:
        """Return a concise run summary."""
        return {
            "id": self.id,
            "script_path": self.script_path,
            "args": self.args,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "exit_code": self.exit_code,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "log_count": len(self.logs),
            "error_count": len(self.errors),
        }


class DaemonState:
    """Central state holder for the daemon server.

    Manages all runs, retaining state across pipeline lifecycles.
    """

    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}
        self.active_run_id: Optional[str] = None
        self._ws_clients: list[Any] = []
        self._lock = asyncio.Lock()
        self._event_notify: asyncio.Condition = asyncio.Condition()
        self._media_store: dict[str, str] = {}  # media_id -> base64 data

    def create_run(
        self,
        script_path: str,
        args: list[str] | None = None,
        run_id: str | None = None,
    ) -> Run:
        """Create a new run entry."""
        if run_id is None:
            run_id = f"run_{int(time.time())}_{len(self.runs)}"

        source_hash = None
        path = Path(script_path)
        if path.exists():
            source_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:12]

        run = Run(
            id=run_id,
            script_path=script_path,
            args=args or [],
            status="starting",
            started_at=datetime.now(),
            source_hash=source_hash,
        )
        self.runs[run_id] = run
        self.active_run_id = run_id
        return run

    def get_active_run(self) -> Optional[Run]:
        """Return the currently active run, if any."""
        if self.active_run_id and self.active_run_id in self.runs:
            run = self.runs[self.active_run_id]
            if run.status == "running":
                return run
        return None

    def get_latest_run(self) -> Optional[Run]:
        """Return the most recent run regardless of status."""
        if self.active_run_id and self.active_run_id in self.runs:
            return self.runs[self.active_run_id]
        if self.runs:
            return list(self.runs.values())[-1]
        return None

    async def ingest_events(self, events: list[dict], run_id: str | None = None) -> None:
        """Ingest a batch of events into the appropriate run."""
        async with self._lock:
            rid = run_id or self.active_run_id
            if not rid or rid not in self.runs:
                # Create run if it doesn't exist yet (script_path updated by run_start event)
                run = self.create_run("direct", run_id=rid)
                rid = run.id

            run = self.runs[rid]
            if run.status == "starting":
                run.status = "running"

            for event in events:
                self._process_event(run, event)

        # Broadcast to WebSocket clients
        for ws in self._ws_clients[:]:
            try:
                await ws.send_json({"type": "batch", "run_id": rid, "events": events})
            except Exception:
                if ws in self._ws_clients:
                    self._ws_clients.remove(ws)

        # Notify any waiters of new significant events
        async with self._event_notify:
            self._event_notify.notify_all()

    def _process_event(self, run: Run, event: dict) -> None:
        """Process a single event into run state."""
        etype = event.get("type", "")
        node_id = event.get("node")

        if etype == "log":
            entry = LogEntry(
                timestamp=event.get("timestamp", time.time()),
                node=node_id,
                message=event.get("message", ""),
                level=event.get("level", "info"),
                step=event.get("step"),
            )
            run.logs.append(entry)
            if node_id and node_id in run.nodes:
                run.nodes[node_id].logs.append(event)

        elif etype == "metric":
            name = event.get("name", "")
            value = event.get("value", 0)
            step = event.get("step", 0)
            if node_id and node_id in run.nodes:
                node = run.nodes[node_id]
                if name not in node.metrics:
                    node.metrics[name] = []
                node.metrics[name].append({"step": step, "value": value})

        elif etype == "progress":
            if node_id and node_id in run.nodes:
                run.nodes[node_id].progress = event.get("data", {})

        elif etype == "error":
            data = event.get("data", event)
            node = run.nodes.get(node_id or data.get("node", ""))
            error = ErrorEntry(
                timestamp=data.get("timestamp", time.time()),
                node_name=data.get("node", node_id or ""),
                node_docstring=node.docstring if node else data.get("docstring"),
                exception_type=data.get("type", ""),
                exception_message=data.get("error", ""),
                traceback=data.get("traceback", ""),
                execution_count=node.exec_count if node else data.get("exec_count", 0),
                params=node.params if node else data.get("params", {}),
                last_logs=[l.get("message", "") for l in (node.logs[-5:] if node else [])],
            )
            run.errors.append(error)
            if node:
                node.errors.append(data)
            run.significant_events.append({
                "type": "error",
                "timestamp": error.timestamp,
                "node": error.node_name,
                "message": error.exception_message,
            })

        elif etype == "node_register":
            data = event.get("data", {})
            nid = data.get("node_id", node_id or "")
            if nid and nid not in run.nodes:
                run.nodes[nid] = NodeState(
                    name=nid,
                    func_name=data.get("func_name", ""),
                    docstring=data.get("docstring"),
                    pausable=data.get("pausable", False),
                )

        elif etype == "node_executed":
            data = event.get("data", {})
            nid = data.get("node_id", node_id or "")
            caller = data.get("caller")
            if nid and nid in run.nodes:
                run.nodes[nid].exec_count += 1
            if caller and nid:
                key = (caller, nid)
                if key not in run._edge_set:
                    run._edge_set.add(key)
                    run.edges.append({"source": caller, "target": nid})
                    if nid in run.nodes:
                        run.nodes[nid].is_source = False

        elif etype == "edge":
            data = event.get("data", {})
            src = data.get("source", "")
            tgt = data.get("target", "")
            key = (src, tgt)
            if key not in run._edge_set:
                run._edge_set.add(key)
                run.edges.append({"source": src, "target": tgt})
                if tgt in run.nodes:
                    run.nodes[tgt].is_source = False

        elif etype == "image":
            if node_id and node_id in run.nodes:
                media_id = uuid.uuid4().hex[:16]
                self._media_store[media_id] = event.pop("data", "")
                event["media_id"] = media_id
                run.nodes[node_id].images.append({
                    "media_id": media_id,
                    "name": event.get("name", ""),
                    "step": event.get("step"),
                    "timestamp": event.get("timestamp", time.time()),
                })

        elif etype == "audio":
            if node_id and node_id in run.nodes:
                media_id = uuid.uuid4().hex[:16]
                self._media_store[media_id] = event.pop("data", "")
                event["media_id"] = media_id
                run.nodes[node_id].audio.append({
                    "media_id": media_id,
                    "name": event.get("name", ""),
                    "sr": event.get("sr", 16000),
                    "step": event.get("step"),
                    "timestamp": event.get("timestamp", time.time()),
                })

        elif etype == "text":
            # Store as a log entry (same as log_text() does locally)
            entry = LogEntry(
                timestamp=event.get("timestamp", time.time()),
                node=node_id,
                message=f"[{event.get('name', '')}] {event.get('content', '')}",
                level="info",
                type="text",
            )
            run.logs.append(entry)
            if node_id and node_id in run.nodes:
                run.nodes[node_id].logs.append(event)

        elif etype == "ask_prompt":
            ask_id = event.get("ask_id") or event.get("data", {}).get("ask_id", "")
            if ask_id:
                run.pending_asks[ask_id] = event
                run.significant_events.append({
                    "type": "ask_prompt",
                    "timestamp": event.get("timestamp", time.time()),
                    "ask_id": ask_id,
                    "question": event.get("question", event.get("data", {}).get("question", "")),
                })

        elif etype == "description":
            desc = event.get("data", {}).get("description", "")
            if run.workflow_description:
                run.workflow_description += "\n\n" + desc
            else:
                run.workflow_description = desc

        elif etype == "config":
            cfg = event.get("data", {})
            run.config = cfg
            if node_id and node_id in run.nodes:
                run.nodes[node_id].params.update(cfg)

        elif etype == "run_start":
            data = event.get("data", {})
            script_path = data.get("script_path", "")
            if script_path:
                run.script_path = script_path

        elif etype == "run_completed":
            data = event.get("data", {})
            exit_code = data.get("exit_code", 0)
            run.status = "completed" if exit_code == 0 else "crashed"
            run.exit_code = exit_code
            run.ended_at = datetime.now()
            run.significant_events.append({
                "type": "run_completed",
                "timestamp": time.time(),
                "exit_code": exit_code,
                "status": run.status,
            })

    def mark_run_completed(self, run_id: str, exit_code: int = 0) -> None:
        """Mark a run as completed."""
        if run_id in self.runs:
            run = self.runs[run_id]
            run.status = "completed" if exit_code == 0 else "crashed"
            run.exit_code = exit_code
            run.ended_at = datetime.now()

    def mark_run_stopped(self, run_id: str) -> None:
        """Mark a run as manually stopped."""
        if run_id in self.runs:
            run = self.runs[run_id]
            run.status = "stopped"
            run.ended_at = datetime.now()


def create_daemon_app(state: DaemonState | None = None, port: int | None = None) -> Any:
    """Create the FastAPI daemon application.

    Args:
        state: Optional pre-existing DaemonState. Creates new if None.
        port: Daemon port for injecting into pipeline subprocess env.
              Falls back to GRAPHBOOK_DAEMON_PORT env var, then 2048.

    Returns:
        FastAPI application instance.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from graphbook.beta.server.runner import PipelineRunner

    if port is None:
        port = int(os.environ.get("GRAPHBOOK_DAEMON_PORT", "2048"))

    if state is None:
        state = DaemonState()

    # --- Pipeline runner wired into daemon state ---
    runner = PipelineRunner(
        on_started=lambda rid: None,  # Run already created in /run handler
        on_completed=lambda rid, code: state.mark_run_completed(rid, code),
        on_output=lambda rid, stream, line: _capture_output(state, rid, stream, line),
    )

    def _capture_output(st: DaemonState, run_id: str, stream: str, line: str) -> None:
        run = st.runs.get(run_id)
        if run:
            if stream == "stdout":
                run.stdout_lines.append(line)
            else:
                run.stderr_lines.append(line)

    app = FastAPI(title="Graphbook Daemon Server")
    app.state.daemon = state
    app.state.runner = runner

    # CORS for development (Vite dev server)
    from starlette.middleware.cors import CORSMiddleware
    from starlette.types import ASGIApp, Receive, Scope, Send

    class CORSWithWebSocket:
        """Wraps CORSMiddleware but lets WebSocket connections pass through."""
        def __init__(self, app: ASGIApp) -> None:
            self.app = app
            self.cors = CORSMiddleware(
                app,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] == "websocket":
                await self.app(scope, receive, send)
            else:
                await self.cors(scope, receive, send)

    app.add_middleware(CORSWithWebSocket)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": time.time(),
            "active_run": state.active_run_id,
            "total_runs": len(state.runs),
        }

    @app.post("/events")
    async def ingest_events(events: list[dict[str, Any]], run_id: str | None = None):
        await state.ingest_events(events, run_id)
        return {"status": "ok", "count": len(events)}

    # Legacy endpoint for backward compat
    @app.post("/ingest")
    async def ingest_legacy(events: list[dict[str, Any]]):
        await state.ingest_events(events)
        return {"status": "ok", "count": len(events)}

    @app.post("/run")
    async def start_run(body: dict[str, Any]):
        """Start a pipeline script as a managed subprocess."""
        script_path = body.get("script_path", "")
        args = body.get("args", [])
        run_id = body.get("run_id") or f"run_{int(time.time())}_{len(state.runs)}"
        if not script_path:
            return JSONResponse(status_code=400, content={"error": "script_path is required"})
        try:
            run = state.create_run(script_path, args, run_id)
            proc = runner.start(
                run_id=run_id,
                script_path=script_path,
                args=args,
                port=port,
            )
            run.process = proc
            run.status = "running"
            return {"run_id": run_id, "pid": proc.pid, "status": "started"}
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"error": str(e)})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/runs/{run_id}/stop")
    async def stop_run(run_id: str):  # noqa: path param only
        """Stop a running pipeline."""
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        exit_code = runner.stop(run_id)
        if exit_code is None and not runner.is_running(run_id):
            state.mark_run_stopped(run_id)
            return {"run_id": run_id, "status": "stopped", "exit_code": None}
        state.mark_run_stopped(run_id)
        return {"run_id": run_id, "status": "stopped", "exit_code": exit_code}

    @app.get("/runs")
    async def list_runs():
        return {
            "runs": [r.get_summary() for r in state.runs.values()],
            "active_run": state.active_run_id,
        }

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        return state.runs[run_id].get_summary()

    @app.get("/runs/{run_id}/graph")
    async def get_run_graph(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        return state.runs[run_id].get_graph()

    @app.get("/runs/{run_id}/logs")
    async def get_run_logs(run_id: str, node: str | None = None, limit: int = 100):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        logs = run.logs
        if node:
            logs = [l for l in logs if l.node == node]
        return {"logs": [{"timestamp": l.timestamp, "node": l.node, "message": l.message, "level": l.level, "step": l.step} for l in logs[-limit:]]}

    @app.get("/runs/{run_id}/errors")
    async def get_run_errors(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        return {
            "errors": [
                {
                    "timestamp": e.timestamp,
                    "node_name": e.node_name,
                    "node_docstring": e.node_docstring,
                    "exception_type": e.exception_type,
                    "exception_message": e.exception_message,
                    "traceback": e.traceback,
                    "execution_count": e.execution_count,
                    "params": e.params,
                    "last_logs": e.last_logs,
                }
                for e in run.errors
            ]
        }

    @app.get("/runs/{run_id}/metrics")
    async def get_run_metrics(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        metrics: dict[str, dict[str, list]] = {}
        for node_id, node in run.nodes.items():
            if node.metrics:
                metrics[node_id] = node.metrics
        return {"metrics": metrics}

    @app.get("/runs/{run_id}/images")
    async def get_run_images(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        images: dict[str, list] = {}
        for node_id, node in run.nodes.items():
            if node.images:
                images[node_id] = [
                    {
                        "node": node_id,
                        "media_id": img.get("media_id", ""),
                        "name": img.get("name", ""),
                        "step": img.get("step"),
                        "timestamp": img.get("timestamp", 0),
                    }
                    for img in node.images
                ]
        return {"images": images}

    @app.get("/runs/{run_id}/audio")
    async def get_run_audio(run_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        audio: dict[str, list] = {}
        for node_id, node in run.nodes.items():
            if node.audio:
                audio[node_id] = [
                    {
                        "node": node_id,
                        "media_id": a.get("media_id", ""),
                        "name": a.get("name", ""),
                        "sr": a.get("sr", 16000),
                        "step": a.get("step"),
                        "timestamp": a.get("timestamp", 0),
                    }
                    for a in node.audio
                ]
        return {"audio": audio}

    @app.get("/runs/{run_id}/media/{media_id}")
    async def get_media(run_id: str, media_id: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        if media_id not in state._media_store:
            return JSONResponse(status_code=404, content={"error": f"Media '{media_id}' not found"})
        return {"data": state._media_store[media_id]}

    @app.get("/runs/{run_id}/nodes/{name}")
    async def get_run_node(run_id: str, name: str):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        run = state.runs[run_id]
        if name not in run.nodes:
            return JSONResponse(status_code=404, content={"error": f"Node '{name}' not found"})
        n = run.nodes[name]
        return {
            "name": n.name, "func_name": n.func_name, "docstring": n.docstring,
            "exec_count": n.exec_count,
            "is_source": n.is_source, "params": n.params,
            "recent_logs": n.logs[-20:], "errors": n.errors,
            "metrics": n.metrics, "progress": n.progress,
        }

    # --- Ask / respond endpoints ---

    def _get_run_or_404(run_id: str):
        if run_id not in state.runs:
            return None, JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})
        return state.runs[run_id], None

    @app.get("/runs/{run_id}/asks")
    async def get_run_asks(run_id: str):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        return {"pending": list(run.pending_asks.values())}

    @app.get("/runs/{run_id}/ask/{ask_id}/respond")
    async def get_ask_response(run_id: str, ask_id: str):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        if ask_id in run.ask_responses:
            return {"status": "answered", "response": run.ask_responses[ask_id]}
        if ask_id in run.pending_asks:
            return {"status": "pending"}
        return JSONResponse(status_code=404, content={"error": f"Ask '{ask_id}' not found"})

    @app.post("/runs/{run_id}/ask/{ask_id}/respond")
    async def post_ask_response(run_id: str, ask_id: str, body: dict):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        response = body.get("response", "")
        run.ask_responses[ask_id] = response
        run.pending_asks.pop(ask_id, None)
        return {"status": "ok"}

    # --- Pause / unpause endpoints ---

    @app.get("/runs/{run_id}/pause")
    async def get_pause_state(run_id: str):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        return {"paused": run.paused}

    @app.post("/runs/{run_id}/pause")
    async def pause_run(run_id: str):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        run.paused = True
        # Broadcast pause state to WebSocket clients
        for ws in state._ws_clients[:]:
            try:
                await ws.send_json({
                    "type": "batch",
                    "run_id": run_id,
                    "events": [{"type": "pause_state", "data": {"paused": True}}],
                })
            except Exception:
                if ws in state._ws_clients:
                    state._ws_clients.remove(ws)
        return {"status": "ok", "paused": True}

    @app.post("/runs/{run_id}/unpause")
    async def unpause_run(run_id: str):
        run, err = _get_run_or_404(run_id)
        if err:
            return err
        run.paused = False
        # Broadcast unpause state to WebSocket clients
        for ws in state._ws_clients[:]:
            try:
                await ws.send_json({
                    "type": "batch",
                    "run_id": run_id,
                    "events": [{"type": "pause_state", "data": {"paused": False}}],
                })
            except Exception:
                if ws in state._ws_clients:
                    state._ws_clients.remove(ws)
        return {"status": "ok", "paused": False}

    # --- Event wait endpoint ---

    @app.get("/runs/{run_id}/events/wait")
    async def wait_for_event(
        run_id: str,
        types: str = "error,run_completed,ask_prompt",
        timeout: float = 300,
        since: float = 0,
    ):
        if run_id not in state.runs:
            return JSONResponse(status_code=404, content={"error": f"Run '{run_id}' not found"})

        wanted = set(t.strip() for t in types.split(","))
        deadline = asyncio.get_event_loop().time() + timeout

        def _find_match() -> Optional[dict]:
            run = state.runs[run_id]
            for evt in run.significant_events:
                if evt["type"] in wanted and evt.get("timestamp", 0) > since:
                    return evt
            return None

        # Check for existing matching events first
        match = _find_match()
        if match:
            return {"status": "event", "event": match}

        # Wait for new events with condition variable
        async with state._event_notify:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    await asyncio.wait_for(
                        state._event_notify.wait(), timeout=remaining
                    )
                except asyncio.TimeoutError:
                    break
                match = _find_match()
                if match:
                    return {"status": "event", "event": match}

        run = state.runs[run_id]
        return {"status": "timeout", "run_status": run.status}

    # Backward-compatible endpoints (use latest run)
    @app.get("/graph")
    async def get_graph():
        run = state.get_latest_run()
        if not run:
            return {"nodes": {}, "edges": [], "workflow_description": None}
        return run.get_graph()

    @app.get("/logs")
    async def get_logs(node: str | None = None, limit: int = 100):
        run = state.get_latest_run()
        if not run:
            return {"logs": []}
        logs = run.logs
        if node:
            logs = [l for l in logs if l.node == node]
        return {"logs": [{"timestamp": l.timestamp, "node": l.node, "message": l.message} for l in logs[-limit:]]}

    @app.get("/errors")
    async def get_errors():
        run = state.get_latest_run()
        if not run:
            return {"errors": []}
        return {
            "errors": [
                {
                    "timestamp": e.timestamp,
                    "node_name": e.node_name,
                    "exception_type": e.exception_type,
                    "exception_message": e.exception_message,
                    "traceback": e.traceback,
                }
                for e in run.errors
            ]
        }

    @app.get("/nodes/{name}")
    async def get_node(name: str):
        run = state.get_latest_run()
        if not run:
            return JSONResponse(status_code=404, content={"error": "No runs"})
        if name not in run.nodes:
            return JSONResponse(status_code=404, content={"error": f"Node '{name}' not found"})
        n = run.nodes[name]
        return {
            "name": n.name, "func_name": n.func_name, "docstring": n.docstring,
            "exec_count": n.exec_count, "is_source": n.is_source, "params": n.params,
            "recent_logs": n.logs[-20:], "errors": n.errors,
        }

    @app.websocket("/stream")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        state._ws_clients.append(ws)
        try:
            while True:
                data = await ws.receive_text()
                events = decode_batch(data)
                await state.ingest_events(events)
        except WebSocketDisconnect:
            if ws in state._ws_clients:
                state._ws_clients.remove(ws)
        except Exception:
            if ws in state._ws_clients:
                state._ws_clients.remove(ws)

    # Serve the web UI static files (must be last — catches all unmatched routes)
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="ui")

    return app

"""Rich-based terminal dashboard for the graphbook daemon.

Shows live pipeline status, run history, progress bars, logs, and errors.
Works in both daemon mode (polling server) and local mode (reading in-process state).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class TerminalDisplay:
    """Live terminal dashboard using Rich.

    In daemon mode, polls the server for state.
    In local mode, reads from the in-process SessionState.
    """

    def __init__(
        self,
        refresh_rate: float = 10.0,
        server_url: Optional[str] = None,
    ) -> None:
        """Initialize the terminal display.

        Args:
            refresh_rate: Display updates per second.
            server_url: If set, poll this server URL for state (daemon mode).
        """
        self._refresh_rate = refresh_rate
        self._server_url = server_url
        self._running = False
        self._paused = threading.Event()
        self._paused.set()  # starts unpaused
        self._thread: Optional[threading.Thread] = None
        self._live = None

    def start(self) -> None:
        """Start the live terminal display."""
        if self._running:
            return
        try:
            from rich.live import Live
            self._running = True
            self._thread = threading.Thread(target=self._display_loop, daemon=True)
            self._thread.start()
        except ImportError:
            pass

    def stop(self) -> None:
        """Stop the terminal display."""
        if not self._running:
            return
        self._running = False
        self._paused.set()  # unblock if paused so the thread can exit
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def pause(self) -> None:
        """Pause live rendering so the terminal is free for user input."""
        if not self._running:
            return
        self._paused.clear()
        # Give the display loop time to exit its Live context
        time.sleep(0.15)

    def resume(self) -> None:
        """Resume live rendering after a pause."""
        self._paused.set()

    def _display_loop(self) -> None:
        """Main display loop."""
        from rich.live import Live
        from rich.console import Console

        console = Console()
        interval = 1.0 / self._refresh_rate

        while self._running:
            # Wait until unpaused (or stop is called)
            self._paused.wait()
            if not self._running:
                break

            with Live(self._render(), console=console, refresh_per_second=self._refresh_rate) as live:
                self._live = live
                while self._running and self._paused.is_set():
                    live.update(self._render())
                    time.sleep(interval)
                # Final update so Live.__exit__ prints the true final state
                live.update(self._render())
                self._live = None

    def _get_state_data(self) -> dict:
        """Get state data from server or in-process state."""
        if self._server_url:
            return self._poll_server()
        return self._read_local_state()

    def _poll_server(self) -> dict:
        """Poll the daemon server for current state."""
        try:
            import httpx
            client = httpx.Client(timeout=2.0)

            health = client.get(f"{self._server_url}/health").json()
            runs_data = client.get(f"{self._server_url}/runs").json()
            runs = runs_data.get("runs", [])
            active_run_id = runs_data.get("active_run")

            graph = {}
            logs = []
            errors = []

            if active_run_id:
                try:
                    graph = client.get(f"{self._server_url}/runs/{active_run_id}/graph").json()
                except Exception:
                    pass
                try:
                    logs_resp = client.get(f"{self._server_url}/runs/{active_run_id}/logs", params={"limit": 10}).json()
                    logs = logs_resp.get("logs", [])
                except Exception:
                    pass
                try:
                    errors_resp = client.get(f"{self._server_url}/runs/{active_run_id}/errors").json()
                    errors = errors_resp.get("errors", [])
                except Exception:
                    pass

            client.close()
            return {
                "runs": runs,
                "active_run_id": active_run_id,
                "graph": graph,
                "logs": logs,
                "errors": errors,
                "mode": "server",
            }
        except Exception:
            return {"runs": [], "active_run_id": None, "graph": {}, "logs": [], "errors": [], "mode": "server"}

    def _read_local_state(self) -> dict:
        """Read from in-process SessionState."""
        from graphbook.beta.core.state import get_state
        from graphbook.beta.core.dag import get_dag_summary

        state = get_state()
        nodes = {}
        for nid, n in state.nodes.items():
            nodes[nid] = {
                "name": n.name,
                "func_name": n.func_name,
                "docstring": n.docstring,
                "exec_count": n.exec_count,
                "is_source": n.is_source,
                "params": n.params,
                "progress": n.progress,
            }

        logs = []
        for nid, n in state.nodes.items():
            for entry in n.logs[-5:]:
                logs.append({
                    "timestamp": entry.get("timestamp", 0),
                    "node": n.func_name,
                    "message": entry.get("message", entry.get("content", "")),
                })
        logs.sort(key=lambda x: x.get("timestamp", 0))

        errors = []
        for nid, n in state.nodes.items():
            for err in n.errors:
                errors.append({
                    "node_name": n.func_name,
                    "exception_type": err.get("type", ""),
                    "exception_message": err.get("error", ""),
                })

        # Check if also forwarding to daemon
        client = state._client
        connected = client is not None and client.is_connected()
        mode = "server" if connected else "local"

        return {
            "runs": [],
            "active_run_id": None,
            "graph": {
                "nodes": nodes,
                "edges": [{"source": e.source, "target": e.target} for e in state.edges],
                "workflow_description": state.workflow_description,
            },
            "logs": logs[-10:],
            "errors": errors,
            "mode": mode,
        }

    def _render(self) -> Any:
        """Render the current state as a Rich renderable."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.console import Group

        data = self._get_state_data()
        parts: list[Any] = []

        mode = data.get("mode", "local")
        graph = data.get("graph", {})
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])
        logs = data.get("logs", [])
        errors = data.get("errors", [])
        runs = data.get("runs", [])

        # ── Mode indicator ──
        if mode == "server":
            parts.append(Text("  Daemon: connected", style="green"))
        else:
            parts.append(Text("  Daemon: not connected", style="yellow"))

        # ── Run history (daemon mode) ──
        if runs:
            parts.append(Text(""))
            parts.append(Text("  Runs:", style="bold"))
            for r in runs[-5:]:
                status = r.get("status", "?")
                icons = {"running": "↻", "completed": "✓", "crashed": "✗", "stopped": "■", "starting": "…"}
                icon = icons.get(status, "?")
                style = {"running": "cyan", "completed": "green", "crashed": "red", "stopped": "dim"}.get(status, "")
                parts.append(Text(f"    {icon} {r.get('id', '?')}: {status} ({r.get('script_path', '?')})", style=style))

        # ── DAG topology ──
        if nodes:
            # Build topology string
            source_names = [n.get("func_name", nid) for nid, n in nodes.items() if n.get("is_source")]
            topo = " → ".join(source_names) if source_names else "..."
            if edges:
                seen = set()
                chain = []
                for e in edges:
                    src = e.get("source", "").split(".")[-1]
                    tgt = e.get("target", "").split(".")[-1]
                    if src not in seen:
                        chain.append(src)
                        seen.add(src)
                    if tgt not in seen:
                        chain.append(tgt)
                        seen.add(tgt)
                if chain:
                    topo = " → ".join(chain)

            parts.append(Text(""))
            parts.append(Text(f"  DAG: {topo}", style="bold cyan"))

        # ── Node progress table ──
        if nodes:
            parts.append(Text(""))
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Node", style="bold", width=22)
            table.add_column("Status", width=10)
            table.add_column("Progress", width=30)

            for nid, node in nodes.items():
                progress = node.get("progress")
                if progress and progress.get("total"):
                    current = progress["current"]
                    total = progress["total"]
                    pct = current / total if total else 0
                    bar_width = 20
                    filled = int(pct * bar_width)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    progress_text = f"[{bar}] {pct * 100:3.0f}%"
                    status = "↻" if pct < 1.0 else "✓"
                else:
                    progress_text = ""
                    exec_count = node.get("exec_count", 0)
                    status = "✓" if exec_count > 0 else "·"

                count = node.get("exec_count", 0)
                name = node.get("func_name", nid)
                if len(name) > 20:
                    name = name[:17] + "..."
                table.add_row(f"  {name}", f"{status} {count}x", progress_text)

            parts.append(table)

        # ── Errors ──
        if errors:
            parts.append(Text(""))
            parts.append(Text(f"  Errors ({len(errors)}):", style="bold red"))
            for err in errors[-3:]:
                node_name = err.get("node_name", "?")
                exc_type = err.get("exception_type", "?")
                exc_msg = err.get("exception_message", "")
                msg = f"{exc_type}: {exc_msg}" if exc_msg else exc_type
                if len(msg) > 70:
                    msg = msg[:67] + "..."
                parts.append(Text(f"    [{node_name}] {msg}", style="red"))

        # ── Recent logs ──
        if logs:
            recent = logs[-8:]
            parts.append(Text(""))
            parts.append(Text("  Recent logs:", style="dim"))
            for entry in recent:
                node_tag = entry.get("node", "")
                if node_tag:
                    node_tag = node_tag.split(".")[-1]
                msg = entry.get("message", "")
                if len(msg) > 70:
                    msg = msg[:67] + "..."
                parts.append(Text(f"    [{node_tag}] {msg}", style="dim"))

        if not parts:
            parts.append(Text("  No pipeline data yet.", style="dim"))

        panel = Panel(
            Group(*parts),
            title="Graphbook",
            border_style="blue",
        )
        return panel

    def render_once(self) -> None:
        """Render a single frame to the console."""
        from rich.console import Console
        console = Console()
        console.print(self._render())

"""Rich-based terminal dashboard for graphbook beta."""

from __future__ import annotations

import threading
import time
from typing import Optional

from graphbook.beta.core.state import get_state


class TerminalDisplay:
    """Live terminal dashboard using Rich."""

    def __init__(self, refresh_rate: float = 10.0) -> None:
        """Initialize the terminal display.

        Args:
            refresh_rate: Display updates per second.
        """
        self._refresh_rate = refresh_rate
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._live = None

    def start(self) -> None:
        """Start the live terminal display."""
        if self._running:
            return

        from rich.live import Live  # noqa: F401 — fail fast if Rich is missing
        self._running = True
        self._thread = threading.Thread(target=self._display_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the terminal display."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _display_loop(self) -> None:
        """Main display loop."""
        from rich.live import Live
        from rich.console import Console

        console = Console()
        interval = 1.0 / self._refresh_rate

        with Live(self._render(), console=console, refresh_per_second=self._refresh_rate) as live:
            self._live = live
            while self._running:
                live.update(self._render())
                time.sleep(interval)

    def _render(self):
        """Render the current state as a Rich renderable."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.console import Group

        state = get_state()
        parts = []

        # DAG topology
        from graphbook.beta.core.dag import get_dag_summary
        dag_text = Text(f"  DAG: {get_dag_summary()}", style="bold cyan")
        parts.append(dag_text)
        parts.append(Text(""))

        # Node progress table
        if state.nodes:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Node", style="bold", width=20)
            table.add_column("Status", width=8)
            table.add_column("Progress", width=30)

            for node_id, node in state.nodes.items():
                # Status indicator
                if node.progress and node.progress.get("total"):
                    current = node.progress["current"]
                    total = node.progress["total"]
                    pct = current / total if total else 0
                    bar_width = 20
                    filled = int(pct * bar_width)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    progress_text = f"[{bar}] {pct * 100:3.0f}%"
                    status = "↻" if pct < 1.0 else "✓"
                else:
                    progress_text = ""
                    status = "✓" if node.exec_count > 0 else "·"

                count_str = f"{status} {node.exec_count}x"
                display_name = node.func_name if len(node.func_name) <= 18 else node.func_name[:15] + "..."
                table.add_row(f"  {display_name}", count_str, progress_text)

            parts.append(table)

        # Recent logs
        all_logs = []
        for node_id, node in state.nodes.items():
            for log_entry in node.logs[-5:]:
                all_logs.append((log_entry.get("timestamp", 0), node.func_name, log_entry.get("message", log_entry.get("content", ""))))

        all_logs.sort(key=lambda x: x[0])
        recent = all_logs[-5:]

        if recent:
            parts.append(Text(""))
            parts.append(Text("  Recent logs:", style="dim"))
            for _, node_name, msg in recent:
                parts.append(Text(f"  [{node_name}] {msg}", style="dim"))

        panel = Panel(
            Group(*parts),
            title="Graphbook",
            border_style="blue",
        )
        return panel

    def render_once(self) -> None:
        """Render a single frame to the console (for non-TTY environments)."""
        from rich.console import Console
        console = Console()
        console.print(self._render())

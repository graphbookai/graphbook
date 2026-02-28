"""Tests for the daemon server state management."""

from __future__ import annotations

import pytest

from graphbook.beta.server.daemon import DaemonState, Run, NodeState, LogEntry, ErrorEntry


class TestDaemonState:
    """Tests for DaemonState run management."""

    def setup_method(self) -> None:
        self.state = DaemonState()

    def test_create_run(self) -> None:
        """Should create a run with correct defaults."""
        run = self.state.create_run("test_script.py", args=["--epochs", "10"])
        assert run.script_path == "test_script.py"
        assert run.args == ["--epochs", "10"]
        assert run.status == "starting"
        assert run.started_at is not None
        assert self.state.active_run_id == run.id

    def test_create_run_custom_id(self) -> None:
        """Should accept a custom run ID."""
        run = self.state.create_run("s.py", run_id="my_run")
        assert run.id == "my_run"
        assert "my_run" in self.state.runs

    def test_get_active_run(self) -> None:
        """Should return the currently running run."""
        run = self.state.create_run("s.py")
        run.status = "running"
        assert self.state.get_active_run() is run

    def test_get_active_run_none_when_not_running(self) -> None:
        """Should return None if no run is in 'running' status."""
        run = self.state.create_run("s.py")
        run.status = "completed"
        assert self.state.get_active_run() is None

    def test_get_latest_run(self) -> None:
        """Should return the most recent run."""
        self.state.create_run("a.py", run_id="r1")
        self.state.create_run("b.py", run_id="r2")
        latest = self.state.get_latest_run()
        assert latest is not None
        assert latest.id == "r2"

    def test_mark_run_completed(self) -> None:
        """Should mark a run as completed with exit code."""
        run = self.state.create_run("s.py", run_id="r1")
        self.state.mark_run_completed("r1", exit_code=0)
        assert run.status == "completed"
        assert run.exit_code == 0
        assert run.ended_at is not None

    def test_mark_run_crashed(self) -> None:
        """Should mark a run as crashed on non-zero exit."""
        run = self.state.create_run("s.py", run_id="r1")
        self.state.mark_run_completed("r1", exit_code=1)
        assert run.status == "crashed"
        assert run.exit_code == 1

    def test_mark_run_stopped(self) -> None:
        """Should mark a run as manually stopped."""
        run = self.state.create_run("s.py", run_id="r1")
        self.state.mark_run_stopped("r1")
        assert run.status == "stopped"


class TestDaemonEventIngestion:
    """Tests for event processing into run state."""

    def setup_method(self) -> None:
        self.state = DaemonState()

    @pytest.mark.asyncio
    async def test_ingest_node_register(self) -> None:
        """Should register nodes from events."""
        run = self.state.create_run("s.py", run_id="r1")
        await self.state.ingest_events([
            {"type": "node_register", "data": {"node_id": "my_func", "func_name": "my_func", "docstring": "Does stuff"}},
        ], "r1")
        assert "my_func" in run.nodes
        assert run.nodes["my_func"].docstring == "Does stuff"
        assert run.status == "running"  # auto-transitions from starting

    @pytest.mark.asyncio
    async def test_ingest_log(self) -> None:
        """Should append log entries."""
        self.state.create_run("s.py", run_id="r1")
        await self.state.ingest_events([
            {"type": "node_register", "data": {"node_id": "n1", "func_name": "n1"}},
            {"type": "log", "node": "n1", "message": "hello world"},
        ], "r1")
        run = self.state.runs["r1"]
        assert len(run.logs) == 1
        assert run.logs[0].message == "hello world"

    @pytest.mark.asyncio
    async def test_ingest_edge(self) -> None:
        """Should track DAG edges and mark targets as non-source."""
        self.state.create_run("s.py", run_id="r1")
        await self.state.ingest_events([
            {"type": "node_register", "data": {"node_id": "a", "func_name": "a"}},
            {"type": "node_register", "data": {"node_id": "b", "func_name": "b"}},
            {"type": "edge", "data": {"source": "a", "target": "b"}},
        ], "r1")
        run = self.state.runs["r1"]
        assert len(run.edges) == 1
        assert run.nodes["a"].is_source is True
        assert run.nodes["b"].is_source is False

    @pytest.mark.asyncio
    async def test_ingest_error(self) -> None:
        """Should capture enriched errors."""
        self.state.create_run("s.py", run_id="r1")
        await self.state.ingest_events([
            {"type": "node_register", "data": {"node_id": "n1", "func_name": "n1", "docstring": "A step"}},
            {"type": "error", "node": "n1", "data": {
                "node": "n1", "type": "ValueError", "error": "bad value",
                "traceback": "Traceback...", "timestamp": 1234,
            }},
        ], "r1")
        run = self.state.runs["r1"]
        assert len(run.errors) == 1
        assert run.errors[0].exception_type == "ValueError"
        assert run.errors[0].node_docstring == "A step"

    @pytest.mark.asyncio
    async def test_ingest_metric(self) -> None:
        """Should store metrics on nodes."""
        self.state.create_run("s.py", run_id="r1")
        await self.state.ingest_events([
            {"type": "node_register", "data": {"node_id": "train", "func_name": "train"}},
            {"type": "metric", "node": "train", "name": "loss", "value": 0.5, "step": 0},
            {"type": "metric", "node": "train", "name": "loss", "value": 0.3, "step": 1},
        ], "r1")
        run = self.state.runs["r1"]
        assert "loss" in run.nodes["train"].metrics
        assert len(run.nodes["train"].metrics["loss"]) == 2

    @pytest.mark.asyncio
    async def test_ingest_creates_implicit_run(self) -> None:
        """Should create an implicit run if none exists."""
        await self.state.ingest_events([
            {"type": "log", "message": "orphan log"},
        ])
        assert len(self.state.runs) == 1


class TestRunSummary:
    """Tests for Run serialization methods."""

    def test_get_summary(self) -> None:
        """Should return a concise summary dict."""
        run = Run(id="r1", script_path="train.py", args=["--lr", "0.01"])
        summary = run.get_summary()
        assert summary["id"] == "r1"
        assert summary["script_path"] == "train.py"
        assert summary["args"] == ["--lr", "0.01"]

    def test_get_graph(self) -> None:
        """Should return serializable graph dict."""
        run = Run(id="r1", script_path="s.py")
        run.nodes["a"] = NodeState(name="a", func_name="a", docstring="Step A")
        run.edges.append({"source": "a", "target": "b"})
        graph = run.get_graph()
        assert "a" in graph["nodes"]
        assert graph["nodes"]["a"]["docstring"] == "Step A"
        assert len(graph["edges"]) == 1

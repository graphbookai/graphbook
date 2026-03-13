"""Tests for the logging API."""

from __future__ import annotations

import pytest

from graphbook.beta.core.state import SessionState, get_state, _current_node
from graphbook.beta.core.decorators import fn
from graphbook.beta.logging.logger import log, log_metric, log_text, md
from graphbook.beta.core.config import log_cfg


class TestLogging:
    """Tests for gb.log(), gb.log_metric(), etc."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_log_inside_step(self) -> None:
        """log() inside a step should attach to that node."""
        @fn()
        def my_step():
            log("hello world")

        my_step()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "my_step")
        assert len(node.logs) == 1
        assert node.logs[0]["message"] == "hello world"

    def test_log_metric_inside_step(self) -> None:
        """log_metric() should store metrics on the node."""
        @fn()
        def train():
            log_metric("loss", 0.5, step=0)
            log_metric("loss", 0.3, step=1)
            log_metric("loss", 0.1, step=2)

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert "loss" in node.metrics
        assert len(node.metrics["loss"]) == 3
        assert node.metrics["loss"][0] == (0, 0.5)
        assert node.metrics["loss"][2] == (2, 0.1)

    def test_log_text(self) -> None:
        """log_text() should store text entries."""
        @fn()
        def report():
            log_text("summary", "## Results\nAll good!")

        report()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "report")
        assert len(node.logs) == 1
        assert node.logs[0]["content"] == "## Results\nAll good!"

    def test_md_sets_workflow_description(self) -> None:
        """md() should set the workflow-level description."""
        md("This is a test workflow")
        state = get_state()
        assert state.workflow_description == "This is a test workflow"

    def test_md_appends(self) -> None:
        """Multiple md() calls should append descriptions."""
        md("Part 1")
        md("Part 2")
        state = get_state()
        assert state.workflow_description is not None
        assert "Part 1" in state.workflow_description
        assert "Part 2" in state.workflow_description


class TestLogNumpy:
    """Tests for log() with numpy arrays."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_log_numpy_array(self) -> None:
        """log() should format numpy arrays with shape, dtype, and stats."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")

        @fn()
        def check_array():
            arr = np.zeros((3, 224, 224), dtype=np.float32)
            log(arr)

        check_array()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "check_array")
        assert len(node.logs) == 1
        msg = node.logs[0]["message"]
        assert "ndarray" in msg
        assert "(3, 224, 224)" in msg
        assert "float32" in msg
        assert "min:" in msg
        assert "max:" in msg
        assert "mean:" in msg

    def test_log_numpy_preserves_string(self) -> None:
        """log() with a plain string should still work as before."""
        @fn()
        def my_step():
            log("plain text message")

        my_step()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "my_step")
        assert node.logs[0]["message"] == "plain text message"


class TestLogCfg:
    """Tests for gb.log_cfg()."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_log_cfg_stores_params(self) -> None:
        """log_cfg() should store config in node params."""
        @fn()
        def train():
            log_cfg({"lr": 0.001, "batch_size": 32})

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert node.params["lr"] == 0.001
        assert node.params["batch_size"] == 32

    def test_log_cfg_merges(self) -> None:
        """Multiple log_cfg() calls should merge into one dict."""
        @fn()
        def train():
            log_cfg({"lr": 0.001})
            log_cfg({"batch_size": 32})

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert node.params["lr"] == 0.001
        assert node.params["batch_size"] == 32

    def test_log_cfg_later_call_overwrites(self) -> None:
        """Later log_cfg() calls should overwrite conflicting keys."""
        @fn()
        def train():
            log_cfg({"lr": 0.001, "epochs": 10})
            log_cfg({"lr": 0.01})

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert node.params["lr"] == 0.01
        assert node.params["epochs"] == 10

    def test_log_cfg_filters_non_serializable(self) -> None:
        """log_cfg() should only keep JSON-serializable values."""
        @fn()
        def train():
            log_cfg({"lr": 0.001, "callback": lambda x: x})

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert "lr" in node.params
        assert "callback" not in node.params

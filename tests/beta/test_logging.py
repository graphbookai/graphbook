"""Tests for the logging API."""

from __future__ import annotations

import pytest

from graphbook.beta.core.state import SessionState, get_state, _current_node
from graphbook.beta.core.decorators import step
from graphbook.beta.logging.logger import log, log_metric, log_text, inspect, md


class TestLogging:
    """Tests for gb.log(), gb.log_metric(), etc."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_log_inside_step(self) -> None:
        """log() inside a step should attach to that node."""
        @step()
        def my_step():
            log("hello world")

        my_step()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "my_step")
        assert len(node.logs) == 1
        assert node.logs[0]["message"] == "hello world"

    def test_log_metric_inside_step(self) -> None:
        """log_metric() should store metrics on the node."""
        @step()
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
        @step()
        def report():
            log_text("summary", "## Results\nAll good!")

        report()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "report")
        assert len(node.logs) == 1
        assert node.logs[0]["content"] == "## Results\nAll good!"

    def test_inspect_dict(self) -> None:
        """inspect() should capture metadata about objects."""
        @step()
        def analyze():
            data = {"a": 1, "b": 2, "c": 3}
            result = inspect(data, "my_dict")
            return result

        metadata = analyze()
        assert metadata["type"] == "dict"
        assert metadata["length"] == 3
        assert metadata["name"] == "my_dict"

    def test_inspect_stores_on_node(self) -> None:
        """inspect() should store the result on the node."""
        @step()
        def check():
            inspect([1, 2, 3, 4], "my_list")

        check()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "check")
        assert "my_list" in node.inspections
        assert node.inspections["my_list"]["length"] == 4

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
        assert "Part 1" in state.workflow_description
        assert "Part 2" in state.workflow_description


class TestInspectNumpy:
    """Tests for inspect() with numpy arrays."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_inspect_numpy_array(self) -> None:
        """inspect() should capture shape and dtype for numpy arrays."""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")

        @step()
        def check_array():
            arr = np.zeros((3, 224, 224), dtype=np.float32)
            return inspect(arr, "image")

        metadata = check_array()
        assert metadata["shape"] == [3, 224, 224]
        assert metadata["dtype"] == "float32"
        assert "min" in metadata
        assert "max" in metadata

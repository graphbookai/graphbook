"""Tests for the @step decorator and DAG inference."""

from __future__ import annotations

import pytest

from graphbook.beta.core.state import SessionState, _current_node, get_state
from graphbook.beta.core.decorators import step
from graphbook.beta.core.dag import get_sources, get_topology_order, get_dag_summary


class TestStepDecorator:
    """Tests for the @gb.step() decorator."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        SessionState.reset_singleton()

    def test_step_registers_node(self) -> None:
        """@step should register the function as a node."""
        @step()
        def my_func():
            """My docstring."""
            return 42

        state = get_state()
        assert "TestStepDecorator.test_step_registers_node.<locals>.my_func" in state.nodes or \
               any("my_func" in nid for nid in state.nodes)

    def test_step_captures_docstring(self) -> None:
        """@step should capture the function's docstring."""
        @step()
        def documented_func():
            """This is a documented function."""
            pass

        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "documented_func")
        assert node.docstring == "This is a documented function."

    def test_step_without_parens(self) -> None:
        """@step without parentheses should work."""
        @step
        def bare_func():
            return 1

        result = bare_func()
        assert result == 1
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "bare_func")
        assert node.exec_count == 1

    def test_step_with_config_key(self) -> None:
        """@step('key') should store the config key."""
        @step("model")
        def model_func():
            pass

        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "model_func")
        assert node.config_key == "model"

    def test_step_increments_count(self) -> None:
        """Each call should increment the execution count."""
        @step()
        def counter_func():
            return True

        counter_func()
        counter_func()
        counter_func()

        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "counter_func")
        assert node.exec_count == 3

    def test_step_preserves_return_value(self) -> None:
        """@step should not modify the return value."""
        @step()
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_step_preserves_exceptions(self) -> None:
        """@step should re-raise exceptions."""
        @step()
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()

    def test_step_captures_errors(self) -> None:
        """@step should capture error info when exceptions occur."""
        @step()
        def error_func():
            """A function that errors."""
            raise RuntimeError("something broke")

        with pytest.raises(RuntimeError):
            error_func()

        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "error_func")
        assert len(node.errors) == 1
        assert node.errors[0]["type"] == "RuntimeError"
        assert "something broke" in node.errors[0]["error"]


class TestDAGInference:
    """Tests for automatic DAG edge and source inference."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_single_node_is_source(self) -> None:
        """A single node with no callers should be a source."""
        @step()
        def standalone():
            return 1

        standalone()
        sources = get_sources()
        node = next(n for n in get_state().nodes.values() if n.func_name == "standalone")
        assert node.is_source is True

    def test_dag_edge_inference(self) -> None:
        """Calling a step from another step should create an edge."""
        @step()
        def producer():
            return consumer()

        @step()
        def consumer():
            return 42

        producer()

        state = get_state()
        assert len(state.edges) > 0
        # Producer should be source, consumer should not
        producer_node = next(n for n in state.nodes.values() if n.func_name == "producer")
        consumer_node = next(n for n in state.nodes.values() if n.func_name == "consumer")
        assert producer_node.is_source is True
        assert consumer_node.is_source is False

    def test_linear_dag(self) -> None:
        """A → B → C should create proper edges and sources."""
        @step()
        def step_a():
            return step_b()

        @step()
        def step_b():
            return step_c()

        @step()
        def step_c():
            return "done"

        step_a()

        state = get_state()
        assert len(state.edges) == 2
        sources = get_sources()
        assert len(sources) == 1
        source_node = state.nodes[sources[0]]
        assert source_node.func_name == "step_a"

    def test_dag_summary(self) -> None:
        """get_dag_summary should return topology string."""
        @step()
        def load():
            return process()

        @step()
        def process():
            return "done"

        load()

        summary = get_dag_summary()
        assert "→" in summary or "load" in summary


class TestConfigInjection:
    """Tests for hydr8 config injection via @step."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_config_injection(self) -> None:
        """Config values should be injected into step params."""
        from graphbook.beta.core.config import configure

        configure({
            "model": {"model_name": "resnet18", "batch_size": 16},
        })

        @step("model")
        def predict(x, model_name: str = "resnet50", batch_size: int = 32):
            return model_name, batch_size

        name, bs = predict("input")
        assert name == "resnet18"
        assert bs == 16

    def test_config_does_not_override_explicit_args(self) -> None:
        """Explicit kwargs should not be overridden by config."""
        from graphbook.beta.core.config import configure

        configure({
            "model": {"model_name": "resnet18"},
        })

        @step("model")
        def predict(x, model_name: str = "resnet50"):
            return model_name

        result = predict("input", model_name="vgg16")
        assert result == "vgg16"

    def test_dot_path_injection(self) -> None:
        """Dot-separated config paths should resolve nested keys."""
        from graphbook.beta.core.config import configure

        configure({
            "db": {"postgres": {"host": "localhost", "port": 5432}},
        })

        @step("db.postgres")
        def connect(host: str = "", port: int = 0):
            return host, port

        host, port = connect()
        assert host == "localhost"
        assert port == 5432

    def test_override_context_manager(self) -> None:
        """hydr8.override should temporarily replace config for testing."""
        from graphbook.beta import override
        from graphbook.beta.core.config import configure

        configure({
            "model": {"lr": 0.001},
        })

        @step("model")
        def train(lr: float = 0.01):
            return lr

        assert train() == 0.001

        with override({"model": {"lr": 0.1}}):
            assert train() == 0.1

        assert train() == 0.001

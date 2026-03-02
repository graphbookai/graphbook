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


class TestDataFlowEdges:
    """Tests for data-flow-aware DAG edge inference."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def _edge_set(self) -> set[tuple[str, str]]:
        state = get_state()
        return {(e.source, e.target) for e in state.edges}

    def _nid(self, func_name: str) -> str:
        state = get_state()
        return next(nid for nid, n in state.nodes.items() if n.func_name == func_name)

    def test_linear_data_flow(self) -> None:
        """Sequential steps passing outputs should create data-flow edges."""
        @step()
        def load_data():
            return [1, 2, 3]

        @step()
        def transform(data):
            return [x * 2 for x in data]

        @step()
        def aggregate(data):
            return sum(data)

        @step()
        def pipeline():
            records = load_data()
            transformed = transform(records)
            return aggregate(transformed)

        pipeline()
        edges = self._edge_set()

        # pipeline -> load_data (fallback: no step-produced args)
        assert (self._nid("pipeline"), self._nid("load_data")) in edges
        # load_data -> transform (data-flow)
        assert (self._nid("load_data"), self._nid("transform")) in edges
        # transform -> aggregate (data-flow)
        assert (self._nid("transform"), self._nid("aggregate")) in edges
        # Parent edges should NOT exist for transform and aggregate
        assert (self._nid("pipeline"), self._nid("transform")) not in edges
        assert (self._nid("pipeline"), self._nid("aggregate")) not in edges
        assert len(get_state().edges) == 3

    def test_fan_out_fan_in(self) -> None:
        """Multiple producers feeding into one consumer."""
        @step()
        def source():
            return {"data": [1, 2, 3]}

        @step()
        def process_a(data):
            return {"a": sum(data["data"])}

        @step()
        def process_b(data):
            return {"b": len(data["data"])}

        @step()
        def merge(a_result, b_result):
            return {**a_result, **b_result}

        @step()
        def pipeline():
            data = source()
            a = process_a(data)
            b = process_b(data)
            return merge(a, b)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("pipeline"), self._nid("source")) in edges
        assert (self._nid("source"), self._nid("process_a")) in edges
        assert (self._nid("source"), self._nid("process_b")) in edges
        assert (self._nid("process_a"), self._nid("merge")) in edges
        assert (self._nid("process_b"), self._nid("merge")) in edges
        assert len(get_state().edges) == 5

    def test_fallback_to_parent_when_no_data_dependency(self) -> None:
        """When a step receives no step-produced args, fall back to parent."""
        @step()
        def child():
            return 42

        @step()
        def parent_step():
            return child()

        parent_step()
        edges = self._edge_set()

        assert (self._nid("parent_step"), self._nid("child")) in edges
        assert len(get_state().edges) == 1

    def test_destructured_tuple_returns(self) -> None:
        """Tuple elements should be tracked as produced by the step."""
        @step()
        def create():
            return ([1, 2], [3, 4])

        @step()
        def use_first(x):
            return sum(x)

        @step()
        def use_second(y):
            return sum(y)

        @step()
        def pipeline():
            a, b = create()
            use_first(a)
            use_second(b)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("create"), self._nid("use_first")) in edges
        assert (self._nid("create"), self._nid("use_second")) in edges

    def test_dict_value_tracking(self) -> None:
        """Dict values should be tracked as produced by the step."""
        @step()
        def create_dataset():
            return {"X": [1, 2], "y": [0, 1]}

        @step()
        def train(features, labels):
            return len(features) + len(labels)

        @step()
        def pipeline():
            dataset = create_dataset()
            return train(dataset["X"], dataset["y"])

        pipeline()
        edges = self._edge_set()

        assert (self._nid("create_dataset"), self._nid("train")) in edges

    def test_none_return_not_tracked(self) -> None:
        """Steps returning None should not create false edges."""
        @step()
        def void_step():
            return None

        @step()
        def another_step(x=None):
            return 42

        @step()
        def pipeline():
            void_step()
            return another_step()

        pipeline()
        edges = self._edge_set()

        assert (self._nid("void_step"), self._nid("another_step")) not in edges

    def test_mixed_data_flow_and_nested_calls(self) -> None:
        """Data-flow edges and nested-call edges should coexist."""
        @step()
        def load():
            return [1, 2, 3]

        @step()
        def process(data):
            return helper()

        @step()
        def helper():
            return "done"

        @step()
        def pipeline():
            data = load()
            return process(data)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("pipeline"), self._nid("load")) in edges
        assert (self._nid("load"), self._nid("process")) in edges
        assert (self._nid("process"), self._nid("helper")) in edges
        assert len(get_state().edges) == 3

    def test_depends_on_with_function_refs(self) -> None:
        """depends_on with function references should create explicit edges."""
        @step()
        def foo():
            return 1

        @step(depends_on=[foo])
        def bar():
            return 2

        @step()
        def pipeline():
            foo()
            bar()

        pipeline()
        edges = self._edge_set()

        assert (self._nid("foo"), self._nid("bar")) in edges
        # bar should NOT have a parent edge since depends_on is set
        assert (self._nid("pipeline"), self._nid("bar")) not in edges

    def test_depends_on_with_strings(self) -> None:
        """depends_on with string node IDs should create explicit edges."""
        @step()
        def alpha():
            return 1

        alpha_id = next(
            nid for nid, n in get_state().nodes.items()
            if n.func_name == "alpha"
        )

        @step(depends_on=[alpha_id])
        def beta():
            return 2

        @step()
        def pipeline():
            alpha()
            beta()

        pipeline()
        edges = self._edge_set()

        assert (self._nid("alpha"), self._nid("beta")) in edges

    def test_depends_on_combined_with_auto_detection(self) -> None:
        """depends_on and auto-detected data-flow should both create edges."""
        @step()
        def setup():
            return "config"

        @step()
        def load():
            return [1, 2, 3]

        @step(depends_on=[setup])
        def process(data):
            return sum(data)

        @step()
        def pipeline():
            setup()
            data = load()
            return process(data)

        pipeline()
        edges = self._edge_set()

        # Explicit depends_on edge
        assert (self._nid("setup"), self._nid("process")) in edges
        # Auto-detected data-flow edge
        assert (self._nid("load"), self._nid("process")) in edges
        # No fallback parent edge (has both explicit + auto deps)
        assert (self._nid("pipeline"), self._nid("process")) not in edges

"""Tests for the @fn decorator and DAG inference."""

from __future__ import annotations

import pytest

import graphbook.beta as gb
from graphbook.beta.core.state import SessionState, _current_node, get_state
from graphbook.beta.core.decorators import fn
from graphbook.beta.core.dag import get_sources, get_topology_order, get_dag_summary


def _reset_gb() -> None:
    """Reset graphbook state and force local mode so tests never contact a daemon."""
    SessionState.reset_singleton()
    gb._auto_init_done = False
    gb.init(mode="local")


class TestFnDecorator:
    """Tests for the @gb.fn() decorator."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        _reset_gb()

    def test_fn_registers_node(self) -> None:
        """@fn should register the function as a node on first execution."""
        @fn()
        def my_func():
            """My docstring."""
            return 42

        state = get_state()
        # Node should NOT be registered at decoration time
        assert not any("my_func" in nid for nid in state.nodes)

        my_func()
        # Node should be registered after first execution
        assert any("my_func" in nid for nid in state.nodes)

    def test_fn_captures_docstring(self) -> None:
        """@fn should capture the function's docstring on first execution."""
        @fn()
        def documented_func():
            """This is a documented function."""
            pass

        documented_func()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "documented_func")
        assert node.docstring == "This is a documented function."

    def test_fn_without_parens(self) -> None:
        """@fn without parentheses should work."""
        @fn
        def bare_func():
            return 1

        result = bare_func()
        assert result == 1
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "bare_func")
        assert node.exec_count == 1

    def test_fn_increments_count(self) -> None:
        """Each call should increment the execution count."""
        @fn()
        def counter_func():
            return True

        counter_func()
        counter_func()
        counter_func()

        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "counter_func")
        assert node.exec_count == 3

    def test_fn_preserves_return_value(self) -> None:
        """@fn should not modify the return value."""
        @fn()
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_fn_preserves_exceptions(self) -> None:
        """@fn should re-raise exceptions."""
        @fn()
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()

    def test_fn_captures_errors(self) -> None:
        """@fn should capture error info when exceptions occur."""
        @fn()
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
        _reset_gb()

    def test_single_node_is_source(self) -> None:
        """A single node with no callers should be a source."""
        @fn()
        def standalone():
            return 1

        standalone()
        sources = get_sources()
        node = next(n for n in get_state().nodes.values() if n.func_name == "standalone")
        assert node.is_source is True

    def test_dag_edge_inference(self) -> None:
        """Calling a node from another node should create an edge."""
        @fn()
        def producer():
            return consumer()

        @fn()
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
        """A -> B -> C should create proper edges and sources."""
        @fn()
        def step_a():
            return step_b()

        @fn()
        def step_b():
            return step_c()

        @fn()
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
        @fn()
        def load():
            return process()

        @fn()
        def process():
            return "done"

        load()

        summary = get_dag_summary()
        assert "→" in summary or "load" in summary


class TestLogCfgWithFn:
    """Tests for log_cfg() working with @fn."""

    def setup_method(self) -> None:
        _reset_gb()

    def test_log_cfg_shows_in_node_params(self) -> None:
        """log_cfg() inside a node should populate node.params."""
        from graphbook.beta.core.config import log_cfg

        @fn()
        def train():
            log_cfg({"model_name": "resnet18", "batch_size": 16})
            return "done"

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert node.params["model_name"] == "resnet18"
        assert node.params["batch_size"] == 16

    def test_log_cfg_merges_across_calls(self) -> None:
        """Multiple log_cfg() calls merge params."""
        from graphbook.beta.core.config import log_cfg

        @fn()
        def train():
            log_cfg({"model_name": "resnet18"})
            log_cfg({"batch_size": 16})
            return "done"

        train()
        state = get_state()
        node = next(n for n in state.nodes.values() if n.func_name == "train")
        assert node.params == {"model_name": "resnet18", "batch_size": 16}


class TestDataFlowEdges:
    """Tests for data-flow-aware DAG edge inference."""

    def setup_method(self) -> None:
        _reset_gb()

    def _edge_set(self) -> set[tuple[str, str]]:
        state = get_state()
        return {(e.source, e.target) for e in state.edges}

    def _nid(self, func_name: str) -> str:
        state = get_state()
        return next(nid for nid, n in state.nodes.items() if n.func_name == func_name)

    def test_linear_data_flow(self) -> None:
        """Sequential nodes passing outputs should create data-flow edges."""
        @fn()
        def load_data():
            return [1, 2, 3]

        @fn()
        def transform(data):
            return [x * 2 for x in data]

        @fn()
        def aggregate(data):
            return sum(data)

        @fn()
        def pipeline():
            records = load_data()
            transformed = transform(records)
            return aggregate(transformed)

        pipeline()
        edges = self._edge_set()

        # pipeline -> load_data (parent, no data-flow args)
        assert (self._nid("pipeline"), self._nid("load_data")) in edges
        # load_data -> transform (data-flow: siblings under pipeline)
        assert (self._nid("load_data"), self._nid("transform")) in edges
        # transform -> aggregate (data-flow: siblings under pipeline)
        assert (self._nid("transform"), self._nid("aggregate")) in edges
        # Parent edges should NOT exist when data-flow covers the relationship
        assert (self._nid("pipeline"), self._nid("transform")) not in edges
        assert (self._nid("pipeline"), self._nid("aggregate")) not in edges
        assert len(get_state().edges) == 3

    def test_fan_out_fan_in(self) -> None:
        """Multiple producers feeding into one consumer."""
        @fn()
        def source():
            return {"data": [1, 2, 3]}

        @fn()
        def process_a(data):
            return {"a": sum(data["data"])}

        @fn()
        def process_b(data):
            return {"b": len(data["data"])}

        @fn()
        def merge(a_result, b_result):
            return {**a_result, **b_result}

        @fn()
        def pipeline():
            data = source()
            a = process_a(data)
            b = process_b(data)
            return merge(a, b)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("pipeline"), self._nid("source")) in edges
        # Data-flow edges between siblings
        assert (self._nid("source"), self._nid("process_a")) in edges
        assert (self._nid("source"), self._nid("process_b")) in edges
        assert (self._nid("process_a"), self._nid("merge")) in edges
        assert (self._nid("process_b"), self._nid("merge")) in edges
        assert len(get_state().edges) == 5

    def test_fallback_to_parent_when_no_data_dependency(self) -> None:
        """When a node receives no node-produced args, fall back to parent."""
        @fn()
        def child():
            return 42

        @fn()
        def parent_step():
            return child()

        parent_step()
        edges = self._edge_set()

        assert (self._nid("parent_step"), self._nid("child")) in edges
        assert len(get_state().edges) == 1

    def test_destructured_tuple_returns(self) -> None:
        """Tuple elements should be tracked as produced by the node."""
        @fn()
        def create():
            return ([1, 2], [3, 4])

        @fn()
        def use_first(x):
            return sum(x)

        @fn()
        def use_second(y):
            return sum(y)

        @fn()
        def pipeline():
            a, b = create()
            use_first(a)
            use_second(b)

        pipeline()
        edges = self._edge_set()

        # Data-flow edges between siblings
        assert (self._nid("create"), self._nid("use_first")) in edges
        assert (self._nid("create"), self._nid("use_second")) in edges

    def test_dict_value_tracking(self) -> None:
        """Dict values should be tracked as produced by the node."""
        @fn()
        def create_dataset():
            return {"X": [1, 2], "y": [0, 1]}

        @fn()
        def train(features, labels):
            return len(features) + len(labels)

        @fn()
        def pipeline():
            dataset = create_dataset()
            return train(dataset["X"], dataset["y"])

        pipeline()
        edges = self._edge_set()

        # Data-flow edge between siblings
        assert (self._nid("create_dataset"), self._nid("train")) in edges

    def test_none_return_not_tracked(self) -> None:
        """Nodes returning None should not create false edges."""
        @fn()
        def void_step():
            return None

        @fn()
        def another_step(x=None):
            return 42

        @fn()
        def pipeline():
            void_step()
            return another_step()

        pipeline()
        edges = self._edge_set()

        assert (self._nid("void_step"), self._nid("another_step")) not in edges

    def test_mixed_data_flow_and_nested_calls(self) -> None:
        """Data-flow edges and nested-call edges should coexist."""
        @fn()
        def load():
            return [1, 2, 3]

        @fn()
        def process(data):
            return helper()

        @fn()
        def helper():
            return "done"

        @fn()
        def pipeline():
            data = load()
            return process(data)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("pipeline"), self._nid("load")) in edges
        # Data-flow edge between siblings
        assert (self._nid("load"), self._nid("process")) in edges
        # Nested call: process -> helper (parent)
        assert (self._nid("process"), self._nid("helper")) in edges
        assert len(get_state().edges) == 3

    def test_depends_on_with_function_refs(self) -> None:
        """depends_on with function references should create explicit edges."""
        @fn()
        def foo():
            return 1

        @fn(depends_on=[foo])
        def bar():
            return 2

        @fn()
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
        @fn()
        def alpha():
            return 1

        # Use qualname directly since nodes register on execution, not decoration
        alpha_id = alpha.__qualname__

        @fn(depends_on=[alpha_id])
        def beta():
            return 2

        @fn()
        def pipeline():
            alpha()
            beta()

        pipeline()
        edges = self._edge_set()

        assert (self._nid("alpha"), self._nid("beta")) in edges

    def test_depends_on_combined_with_auto_detection(self) -> None:
        """depends_on and auto-detected data-flow should both create edges."""
        @fn()
        def setup():
            return "config"

        @fn()
        def load():
            return [1, 2, 3]

        @fn(depends_on=[setup])
        def process(data):
            return sum(data)

        @fn()
        def pipeline():
            setup()
            data = load()
            return process(data)

        pipeline()
        edges = self._edge_set()

        # Explicit depends_on edge
        assert (self._nid("setup"), self._nid("process")) in edges
        # Auto-detected data-flow edge (siblings under pipeline)
        assert (self._nid("load"), self._nid("process")) in edges
        # No parent edge when depends_on is set
        assert (self._nid("pipeline"), self._nid("process")) not in edges

    def test_object_passthrough_creates_short_edges(self) -> None:
        """An object passed through a parent creates one edge per hop.

        create_model produces `model` (hop 1: create_model -> train),
        train passes it to train_step (hop 2: train -> train_step).
        No long-range edge create_model -> train_step should exist.
        """
        @fn()
        def create_model():
            return {"weights": [1, 2, 3]}

        @fn()
        def train_step(model, batch):
            return sum(model["weights"]) + sum(batch)

        @fn()
        def train(model):
            batch = [10, 20]  # local data, not from a node
            return train_step(model, batch)

        @fn()
        def run_experiment():
            model = create_model()
            return train(model)

        run_experiment()
        edges = self._edge_set()

        # run_experiment -> create_model (parent, no data-flow args)
        assert (self._nid("run_experiment"), self._nid("create_model")) in edges
        # create_model -> train (data-flow: siblings under run_experiment)
        assert (self._nid("create_model"), self._nid("train")) in edges
        # train -> train_step (parent: model passes through train)
        assert (self._nid("train"), self._nid("train_step")) in edges
        # create_model -> train_step should NOT exist (skips a level)
        assert (self._nid("create_model"), self._nid("train_step")) not in edges
        assert len(get_state().edges) == 3

    def test_sibling_data_flow_creates_edge(self) -> None:
        """Data-flow edges connect siblings (nodes sharing same parent)."""
        @fn()
        def produce():
            return [1, 2, 3]

        @fn()
        def consume(data):
            return sum(data)

        @fn()
        def orchestrator():
            data = produce()
            return consume(data)

        orchestrator()
        edges = self._edge_set()

        # orchestrator -> produce (parent, no data-flow args)
        assert (self._nid("orchestrator"), self._nid("produce")) in edges
        # produce -> consume (data-flow: siblings under orchestrator)
        assert (self._nid("produce"), self._nid("consume")) in edges
        # Parent edge should NOT duplicate when data-flow covers it
        assert len(get_state().edges) == 2


class TestDAGStrategy:
    """Tests for configurable DAG strategy."""

    def setup_method(self) -> None:
        _reset_gb()

    def _edge_set(self) -> set[tuple[str, str]]:
        state = get_state()
        return {(e.source, e.target) for e in state.edges}

    def _nid(self, func_name: str) -> str:
        state = get_state()
        return next(nid for nid, n in state.nodes.items() if n.func_name == func_name)

    def test_default_strategy_is_object(self) -> None:
        """Default dag_strategy should be 'object'."""
        state = get_state()
        assert state.dag_strategy == "object"

    def test_stack_strategy_uses_parent_edges_only(self) -> None:
        """Stack strategy should only create caller->callee edges."""
        state = get_state()
        state.dag_strategy = "stack"

        @fn()
        def load():
            return [1, 2, 3]

        @fn()
        def transform(data):
            return [x * 2 for x in data]

        @fn()
        def pipeline():
            data = load()
            return transform(data)

        pipeline()
        edges = self._edge_set()

        # Only parent edges
        assert (self._nid("pipeline"), self._nid("load")) in edges
        assert (self._nid("pipeline"), self._nid("transform")) in edges
        # No data-flow edge
        assert (self._nid("load"), self._nid("transform")) not in edges
        assert len(get_state().edges) == 2

    def test_stack_strategy_fan_out(self) -> None:
        """Stack strategy fan-out: all children get parent edges, no data-flow."""
        state = get_state()
        state.dag_strategy = "stack"

        @fn()
        def source():
            return {"data": [1, 2]}

        @fn()
        def branch_a(data):
            return sum(data["data"])

        @fn()
        def branch_b(data):
            return len(data["data"])

        @fn()
        def pipeline():
            data = source()
            branch_a(data)
            branch_b(data)

        pipeline()
        edges = self._edge_set()

        assert (self._nid("pipeline"), self._nid("source")) in edges
        assert (self._nid("pipeline"), self._nid("branch_a")) in edges
        assert (self._nid("pipeline"), self._nid("branch_b")) in edges
        # No data-flow edges
        assert (self._nid("source"), self._nid("branch_a")) not in edges
        assert (self._nid("source"), self._nid("branch_b")) not in edges
        assert len(get_state().edges) == 3

    def test_both_strategy_creates_parent_and_dataflow_edges(self) -> None:
        """Both strategy should create parent AND data-flow edges."""
        state = get_state()
        state.dag_strategy = "both"

        @fn()
        def load():
            return [1, 2, 3]

        @fn()
        def transform(data):
            return [x * 2 for x in data]

        @fn()
        def pipeline():
            data = load()
            return transform(data)

        pipeline()
        edges = self._edge_set()

        # Parent edges
        assert (self._nid("pipeline"), self._nid("load")) in edges
        assert (self._nid("pipeline"), self._nid("transform")) in edges
        # Data-flow edge
        assert (self._nid("load"), self._nid("transform")) in edges
        assert len(get_state().edges) == 3

    def test_both_strategy_with_depends_on(self) -> None:
        """Both strategy: depends_on, parent, and data-flow edges all coexist."""
        state = get_state()
        state.dag_strategy = "both"

        @fn()
        def setup():
            return "config"

        @fn()
        def load():
            return [1, 2, 3]

        @fn(depends_on=[setup])
        def process(data):
            return sum(data)

        @fn()
        def pipeline():
            setup()
            data = load()
            return process(data)

        pipeline()
        edges = self._edge_set()

        # Explicit depends_on edge
        assert (self._nid("setup"), self._nid("process")) in edges
        # Parent edge (both strategy always adds parent)
        assert (self._nid("pipeline"), self._nid("process")) in edges
        # Data-flow edge
        assert (self._nid("load"), self._nid("process")) in edges

    def test_none_strategy_disables_edges(self) -> None:
        """None strategy should create no automatic edges."""
        state = get_state()
        state.dag_strategy = "none"

        @fn()
        def load():
            return [1, 2, 3]

        @fn()
        def transform(data):
            return [x * 2 for x in data]

        @fn()
        def pipeline():
            data = load()
            return transform(data)

        pipeline()

        # No edges at all — depends_on would still work, but auto-inference is off
        assert len(get_state().edges) == 0

    def test_reset_clears_dag_strategy(self) -> None:
        """reset() should restore dag_strategy to default 'object'."""
        state = get_state()
        state.dag_strategy = "stack"
        assert state.dag_strategy == "stack"
        state.reset()
        assert state.dag_strategy == "object"

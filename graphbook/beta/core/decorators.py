"""The @fn decorator for graphbook beta."""

from __future__ import annotations

import functools
import time
import traceback
from typing import Any, Callable, Optional, TypeVar, overload

from graphbook.beta.core.state import _current_node, get_state

F = TypeVar("F", bound=Callable[..., Any])


@overload
def fn(func: F) -> F: ...


@overload
def fn(
    depends_on: Optional[list[Any]] = None,
    pausable: bool = False,
) -> Callable[[F], F]: ...


def fn(
    func: Optional[Any] = None,
    depends_on: Optional[list[Any]] = None,
    pausable: bool = False,
) -> Any:
    """Decorator that registers a function as a DAG node.

    Can be used as::

        @gb.fn
        @gb.fn()
        @gb.fn(depends_on=[other_fn])
        @gb.fn(pausable=True)

    DAG edges are inferred automatically from data flow between
    **sibling** nodes (nodes sharing the same parent/caller). An object
    creates one edge per hop—if node X produces a value that flows
    through node Y to node A, the edges are X->Y and Y->A, never X->A.
    When no sibling data-flow is detected, a parent edge is used.

    For dependencies that cannot be detected automatically (shared mutable
    state, class attributes, globals), use ``depends_on``::

        @gb.fn(depends_on=[foo])
        def bar(self):
            # bar depends on foo via shared state, not via arguments
            ...

    Args:
        func: The function to decorate (when used without parentheses).
        depends_on: Optional list of decorated functions or node ID strings
            that this node depends on. Creates explicit edges.
        pausable: If True, the function will block before execution when
            the web client sends a pause event. Default is False.

    Returns:
        The decorated function.
    """
    def decorator(f: F) -> F:
        node_id = f.__qualname__
        registered = False

        # Resolve depends_on to node ID strings at decoration time
        depends_on_ids: list[str] = []
        if depends_on:
            for dep in depends_on:
                if callable(dep):
                    depends_on_ids.append(dep.__qualname__)
                else:
                    depends_on_ids.append(str(dep))

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal registered
            # Auto-init on first execution
            try:
                from graphbook.beta import _ensure_init
                _ensure_init()
            except ImportError:
                pass
            state = get_state()
            # Register node on first execution (not at import time)
            if not registered:
                state.register_node(
                    node_id=node_id,
                    func_name=f.__name__,
                    docstring=f.__doc__,
                    pausable=pausable,
                )
                registered = True
            state.ensure_display()
            parent = _current_node.get()
            token = _current_node.set(node_id)
            try:
                # Record DAG edges (data-flow-aware)
                # 1. Explicit depends_on edges (always added)
                if depends_on_ids:
                    for dep in depends_on_ids:
                        state.add_edge(dep, node_id)

                # Record this node's parent for sibling filtering
                state._node_parents[node_id] = parent
                strategy = state.dag_strategy

                # 2. Strategy-dependent edge inference
                if strategy == "none":
                    pass
                elif strategy == "stack":
                    if parent is not None:
                        state.add_edge(parent, node_id)
                elif strategy == "both":
                    if parent is not None:
                        state.add_edge(parent, node_id)
                    producers = state.find_producers(args, kwargs, parent)
                    for producer in producers:
                        state.add_edge(producer, node_id)
                else:  # "object" (default)
                    producers = state.find_producers(args, kwargs, parent)
                    if producers:
                        for producer in producers:
                            state.add_edge(producer, node_id)
                    elif parent is not None and not depends_on_ids:
                        state.add_edge(parent, node_id)

                # Notify backends
                node_info = state.nodes.get(node_id)
                params = node_info.params if node_info else {}
                for backend in state.backends:
                    try:
                        backend.on_node_start(node_id, params)
                    except Exception:
                        pass

                # Block if paused (only for pausable functions)
                if pausable:
                    state.wait_if_paused()

                state.increment_count(node_id)
                start_time = time.monotonic()
                result = f(*args, **kwargs)
                duration = time.monotonic() - start_time

                # Track return value for data-flow edge inference
                state.track_return(node_id, result)

                # Notify backends of completion
                for backend in state.backends:
                    try:
                        backend.on_node_end(node_id, duration)
                    except Exception:
                        pass

                return result
            except Exception as exc:
                # Capture exception with context
                node_info = state.nodes.get(node_id)
                error_info = {
                    "node": node_id,
                    "docstring": node_info.docstring if node_info else None,
                    "exec_count": node_info.exec_count if node_info else 0,
                    "params": node_info.params if node_info else {},
                    "traceback": traceback.format_exc(),
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "timestamp": time.time(),
                }
                if node_info:
                    node_info.errors.append(error_info)

                # Send to queue if available
                if state._queue is not None:
                    try:
                        state._queue.put_event({
                            "type": "error",
                            "data": error_info,
                        })
                    except Exception:
                        pass

                raise  # Re-raise original exception
            finally:
                _current_node.reset(token)

        return wrapper  # type: ignore

    # Handle @fn, @fn()
    if func is None:
        return decorator
    if callable(func):
        return decorator(func)
    raise TypeError(
        f"fn() got an unexpected positional argument {func!r}. "
        "Use @gb.fn or @gb.fn() instead."
    )

"""The @step decorator for graphbook beta."""

from __future__ import annotations

import functools
import time
import traceback
from typing import Any, Callable, Optional, TypeVar, overload

import hydr8

from graphbook.beta.core.state import _current_node, get_state

F = TypeVar("F", bound=Callable[..., Any])


@overload
def step(func: F) -> F: ...


@overload
def step(config_key: Optional[str] = None) -> Callable[[F], F]: ...


def step(func: Optional[Any] = None, config_key: Optional[str] = None) -> Any:
    """Decorator that registers a function as a DAG node.

    Can be used as:
        @gb.step
        @gb.step()
        @gb.step("config_key")

    Args:
        func: The function to decorate (when used without parentheses).
        config_key: Optional config key for hydr8-style param injection.

    Returns:
        The decorated function.
    """
    def decorator(fn: F) -> F:
        node_id = fn.__qualname__
        docstring = fn.__doc__
        state = get_state()
        state.register_node(
            node_id=node_id,
            func_name=fn.__name__,
            docstring=docstring,
            config_key=config_key,
        )

        # Delegate config injection to hydr8
        injected_fn = hydr8.use(config_key)(fn) if config_key else fn

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Auto-init on first step execution if env vars are set
            try:
                from graphbook.beta import _ensure_init
                _ensure_init()
            except ImportError:
                pass
            state = get_state()
            state.ensure_display()
            parent = _current_node.get()
            token = _current_node.set(node_id)
            try:
                # Record DAG edge
                if parent is not None:
                    state.add_edge(parent, node_id)

                # Store resolved config params for UI visibility
                if config_key:
                    try:
                        cfg = dict(hydr8.use(config_key))
                        node_info = state.nodes.get(node_id)
                        if node_info:
                            node_info.params = {
                                k: v for k, v in cfg.items()
                                if isinstance(v, (str, int, float, bool, list, dict))
                            }
                    except Exception:
                        pass

                # Notify backends
                node_info = state.nodes.get(node_id)
                params = node_info.params if node_info else {}
                for backend in state.backends:
                    try:
                        backend.on_node_start(node_id, params)
                    except Exception:
                        pass

                state.increment_count(node_id)
                start_time = time.monotonic()
                result = injected_fn(*args, **kwargs)
                duration = time.monotonic() - start_time

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

    # Handle @step, @step(), @step("key")
    if func is None:
        return decorator
    if callable(func):
        return decorator(func)
    # func is actually the config_key string
    return step(config_key=func)

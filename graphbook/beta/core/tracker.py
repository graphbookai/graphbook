"""tqdm-like iterable progress tracker."""

from __future__ import annotations

import time
from typing import Any, Iterable, Iterator, Optional, TypeVar

from graphbook.beta.core.state import _current_node, get_state

T = TypeVar("T")


class TrackedIterable(Iterator[T]):
    """Wraps an iterable to track progress."""

    def __init__(
        self,
        iterable: Iterable[T],
        name: Optional[str] = None,
        total: Optional[int] = None,
    ) -> None:
        self._iterable = iter(iterable)
        self._name = name
        self._total = total
        self._current = 0
        self._start_time = time.monotonic()
        self._node_id = _current_node.get()

        # Try to infer total from iterable
        if self._total is None:
            try:
                self._total = len(iterable)  # type: ignore
            except (TypeError, AttributeError):
                pass

        # If not inside a @fn node, create an implicit node
        state = get_state()
        if self._node_id is None and self._name:
            self._node_id = f"_track_{self._name}"
            state.register_node(
                node_id=self._node_id,
                func_name=self._name,
                docstring=f"Tracking progress for {self._name}",
            )

        self._update_progress()

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        try:
            value = next(self._iterable)
            self._current += 1
            self._update_progress()
            return value
        except StopIteration:
            self._update_progress()
            raise

    def _update_progress(self) -> None:
        """Update progress state on the current node."""
        if self._node_id is None:
            return
        state = get_state()
        node = state.nodes.get(self._node_id)
        if node is not None:
            node.progress = {
                "current": self._current,
                "total": self._total,
                "name": self._name,
                "elapsed": time.monotonic() - self._start_time,
            }
            # Send progress to queue
            if state._queue is not None:
                try:
                    state._queue.put_event({
                        "type": "progress",
                        "node": self._node_id,
                        "data": node.progress,
                    })
                except Exception:
                    pass


def track(
    iterable: Iterable[T],
    name: Optional[str] = None,
    total: Optional[int] = None,
) -> TrackedIterable[T]:
    """Wrap an iterable to track progress, like tqdm.

    Args:
        iterable: The iterable to wrap.
        name: Display name for the progress bar.
        total: Total number of items (auto-detected if possible).

    Returns:
        A TrackedIterable that reports progress.
    """
    return TrackedIterable(iterable, name=name, total=total)

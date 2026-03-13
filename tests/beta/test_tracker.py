"""Tests for the progress tracker."""

from __future__ import annotations

import pytest

from graphbook.beta.core.state import SessionState, get_state
from graphbook.beta.core.tracker import track
from graphbook.beta.core.decorators import fn


class TestTracker:
    """Tests for gb.track() iterable wrapper."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    def test_track_iterates_all_items(self) -> None:
        """track() should yield all items from the iterable."""
        items = list(track([1, 2, 3, 4, 5], name="test"))
        assert items == [1, 2, 3, 4, 5]

    def test_track_infers_total_from_list(self) -> None:
        """track() should auto-detect total from a list."""
        data = [10, 20, 30]
        tracker = track(data, name="sized")
        assert tracker._total == 3

    def test_track_handles_generator(self) -> None:
        """track() should work with generators (no total)."""
        def gen():
            yield 1
            yield 2
            yield 3

        items = list(track(gen(), name="gen"))
        assert items == [1, 2, 3]

    def test_track_updates_progress(self) -> None:
        """track() should update progress on the bound node."""
        @fn()
        def process_data():
            results = []
            for item in track([1, 2, 3], name="data"):
                results.append(item)
            return results

        result = process_data()
        assert result == [1, 2, 3]

    def test_track_with_explicit_total(self) -> None:
        """track() should accept an explicit total."""
        def gen():
            yield "a"
            yield "b"

        tracker = track(gen(), name="explicit", total=2)
        assert tracker._total == 2
        items = list(tracker)
        assert items == ["a", "b"]

    def test_track_creates_implicit_node(self) -> None:
        """track() at top level should create an implicit node."""
        items = list(track([1, 2], name="toplevel"))
        state = get_state()
        assert any("toplevel" in nid for nid in state.nodes)

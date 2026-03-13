"""Configuration logging for graphbook beta."""

from __future__ import annotations

from typing import Any

from graphbook.beta.core.state import _current_node, get_state


def log_cfg(cfg: dict[str, Any]) -> None:
    """Log configuration for the current node.

    Merges *cfg* into the current node's ``params`` dict so the
    info tab displays all configuration in one place.  Calling
    ``log_cfg`` multiple times within the same node merges
    the dictionaries together (later calls win on key conflicts).

    Args:
        cfg: A flat or nested dictionary of configuration values.
             Only JSON-serializable values (str, int, float, bool,
             list, dict) are retained.

    Example::

        @gb.fn()
        def train(data):
            gb.log_cfg({"model": "resnet50", "batch_size": 32})
            gb.log_cfg({"lr": 0.001})
            # info tab shows: model=resnet50, batch_size=32, lr=0.001
    """
    state = get_state()
    node_id = _current_node.get()

    filtered = {
        k: v for k, v in cfg.items()
        if isinstance(v, (str, int, float, bool, list, dict))
    }

    if node_id and node_id in state.nodes:
        node_info = state.nodes[node_id]
        node_info.params = {**node_info.params, **filtered}

    state._send_to_client({
        "type": "config",
        "node": node_id,
        "data": filtered,
    })

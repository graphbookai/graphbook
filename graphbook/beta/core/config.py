"""Configuration management wrapping hydr8."""

from __future__ import annotations

from typing import Any

from graphbook.beta.core.state import get_state


def configure(config: dict[str, Any]) -> None:
    """Set the global configuration dictionary.

    Config values are injected into @step functions that specify a config_key.
    Only serializable values (str, int, float, bool, list, dict) are shown in the UI.

    Args:
        config: A nested dictionary of configuration values.

    Example:
        gb.configure({
            "model": {"model_name": "resnet50", "batch_size": 32},
            "data": {"path": "/data/imagenet"},
        })
    """
    state = get_state()
    state.config = config

    # Try hydr8 integration if available
    try:
        import hydr8
        hydr8.init(config)
    except ImportError:
        pass

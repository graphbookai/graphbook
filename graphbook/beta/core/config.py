"""Configuration management wrapping hydr8."""

from __future__ import annotations

from typing import Any

import hydr8
from omegaconf import DictConfig, OmegaConf

from graphbook.beta.core.state import get_state


def configure(config: dict[str, Any] | DictConfig) -> None:
    """Set the global configuration dictionary.

    Config values are injected into @step functions via hydr8.
    Only serializable values (str, int, float, bool, list, dict) are shown in the UI.

    Args:
        config: A nested dictionary or OmegaConf DictConfig of configuration values.

    Example:
        gb.configure({
            "model": {"model_name": "resnet50", "batch_size": 32},
            "data": {"path": "/data/imagenet"},
        })
    """
    state = get_state()
    state.config = config if isinstance(config, dict) else OmegaConf.to_container(config, resolve=True)
    if isinstance(config, DictConfig):
        hydr8.init(config)
    else:
        hydr8.init(OmegaConf.create(config))

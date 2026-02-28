"""Logging functions for graphbook beta."""

from __future__ import annotations

import time
from typing import Any, Optional

from graphbook.beta.core.state import _current_node, get_state


def log(message: str) -> None:
    """Log a text message to the current node.

    Args:
        message: The message to log.
    """
    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()

    entry = {
        "type": "log",
        "node": node_id,
        "message": message,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].logs.append(entry)

    for backend in state.backends:
        try:
            backend.on_log(node_id or "", message, timestamp)
        except Exception:
            pass

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_metric(name: str, value: float, step: Optional[int] = None) -> None:
    """Log a scalar metric value.

    Args:
        name: The metric name.
        value: The scalar value.
        step: Optional step counter.
    """
    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()

    if step is None:
        # Auto-increment step
        if node_id and node_id in state.nodes:
            node = state.nodes[node_id]
            if name not in node.metrics:
                node.metrics[name] = []
            step = len(node.metrics[name])

    entry = {
        "type": "metric",
        "node": node_id,
        "name": name,
        "value": value,
        "step": step,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        node = state.nodes[node_id]
        if name not in node.metrics:
            node.metrics[name] = []
        node.metrics[name].append((step, value))

    for backend in state.backends:
        try:
            backend.on_metric(node_id or "", name, value, step or 0)
        except Exception:
            pass

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_image(name: str, image: Any, step: Optional[int] = None) -> None:
    """Log an image (PIL, numpy array, or torch tensor).

    Args:
        name: The image name/label.
        image: The image data.
        step: Optional step counter.
    """
    from graphbook.beta.logging.serializers import serialize_image

    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()
    image_bytes = serialize_image(image)

    entry = {
        "type": "image",
        "node": node_id,
        "name": name,
        "data": image_bytes,
        "step": step,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].images.append({"name": name, "step": step, "timestamp": timestamp})

    for backend in state.backends:
        try:
            backend.on_image(node_id or "", name, image_bytes, step or 0)
        except Exception:
            pass

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_audio(name: str, audio: Any, sr: int = 16000) -> None:
    """Log audio data.

    Args:
        name: The audio clip name.
        audio: Audio data as numpy array.
        sr: Sample rate.
    """
    from graphbook.beta.logging.serializers import serialize_audio

    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()
    audio_bytes = serialize_audio(audio, sr)

    entry = {
        "type": "audio",
        "node": node_id,
        "name": name,
        "data": audio_bytes,
        "sr": sr,
        "timestamp": timestamp,
    }

    for backend in state.backends:
        try:
            backend.on_audio(node_id or "", name, audio_bytes, sr)
        except Exception:
            pass

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_text(name: str, text: str) -> None:
    """Log rich text or markdown content.

    Args:
        name: The text name/label.
        text: The text/markdown content.
    """
    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()

    entry = {
        "type": "text",
        "node": node_id,
        "name": name,
        "content": text,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].logs.append(entry)

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def inspect(obj: Any, name: Optional[str] = None) -> dict:
    """Inspect an object and log its metadata (shape, dtype, etc.).

    Does NOT log raw data — only metadata.

    Args:
        obj: The object to inspect.
        name: Optional name for the inspection.

    Returns:
        Dictionary of metadata about the object.
    """
    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()

    metadata: dict[str, Any] = {"name": name, "type": type(obj).__name__}

    # Shape
    if hasattr(obj, "shape"):
        metadata["shape"] = list(obj.shape)
    elif hasattr(obj, "__len__"):
        try:
            metadata["length"] = len(obj)
        except Exception:
            pass

    # Dtype
    if hasattr(obj, "dtype"):
        metadata["dtype"] = str(obj.dtype)

    # Device (for torch tensors)
    if hasattr(obj, "device"):
        metadata["device"] = str(obj.device)

    # Requires grad (for torch tensors)
    if hasattr(obj, "requires_grad"):
        metadata["requires_grad"] = obj.requires_grad

    # Min/max/mean for numeric types
    try:
        if hasattr(obj, "min") and hasattr(obj, "max"):
            metadata["min"] = float(obj.min())
            metadata["max"] = float(obj.max())
        if hasattr(obj, "mean"):
            metadata["mean"] = float(obj.mean())
    except Exception:
        pass

    # DataFrame info
    if hasattr(obj, "columns") and hasattr(obj, "dtypes"):
        metadata["columns"] = list(obj.columns)
        metadata["dtypes"] = {str(k): str(v) for k, v in obj.dtypes.items()}

    entry = {
        "type": "inspection",
        "node": node_id,
        "data": metadata,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].inspections[name or "unnamed"] = metadata

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass

    return metadata


def md(description: str) -> None:
    """Set or append to the workflow-level description.

    This is distinct from node-level docstrings — it describes the overall workflow.

    Args:
        description: Markdown description of the workflow.
    """
    state = get_state()
    if state.workflow_description is None:
        state.workflow_description = description
    else:
        state.workflow_description += "\n\n" + description

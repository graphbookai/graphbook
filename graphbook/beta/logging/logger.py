"""Logging functions for graphbook beta."""

from __future__ import annotations

import time
from typing import Any, Optional, Union

from graphbook.beta.core.state import _current_node, get_state


def _ensure_initialized() -> None:
    """Trigger auto-init if not yet initialized."""
    try:
        from graphbook.beta import _ensure_init
        _ensure_init()
    except ImportError:
        pass


def _is_tensor_like(obj: Any) -> bool:
    """Check if obj is a numpy ndarray or torch Tensor."""
    type_name = type(obj).__name__
    module = type(obj).__module__ or ""
    if type_name == "ndarray" and "numpy" in module:
        return True
    if type_name == "Tensor" and "torch" in module:
        return True
    return False


def _format_tensor(obj: Any) -> str:
    """Format a tensor-like object into a readable markdown string.

    Includes type, shape, dtype, and basic statistics (min/max/mean)
    so the log tab in the UI displays it nicely.
    """
    parts: list[str] = []
    type_name = type(obj).__name__
    module = type(obj).__module__ or ""

    # Header
    if "torch" in module:
        parts.append(f"**Tensor** (`torch.{type_name}`)")
    else:
        parts.append(f"**ndarray** (`numpy.{type_name}`)")

    # Shape
    if hasattr(obj, "shape"):
        parts.append(f"  shape: `{tuple(obj.shape)}`")

    # Dtype
    if hasattr(obj, "dtype"):
        parts.append(f"  dtype: `{obj.dtype}`")

    # Device (torch only)
    if hasattr(obj, "device"):
        parts.append(f"  device: `{obj.device}`")

    # Requires grad (torch only)
    if hasattr(obj, "requires_grad"):
        parts.append(f"  requires_grad: `{obj.requires_grad}`")

    # Statistics
    try:
        if hasattr(obj, "min") and hasattr(obj, "max"):
            min_val = float(obj.min())
            max_val = float(obj.max())
            parts.append(f"  min: `{min_val:.6g}`, max: `{max_val:.6g}`")
        if hasattr(obj, "mean"):
            mean_val = float(obj.mean())
            parts.append(f"  mean: `{mean_val:.6g}`")
    except Exception:
        pass

    return "\n".join(parts)


def log(message: Union[str, Any], *, step: Optional[int] = None) -> None:
    """Log a message to the current node.

    Accepts plain strings as well as tensor-like objects (numpy
    ndarray, torch Tensor).  Tensor-like objects are automatically
    formatted with shape, dtype, and basic statistics so they
    display nicely in the UI log tab.

    Args:
        message: The message string, or a tensor/ndarray to format.
        step: Optional step counter.
    """
    _ensure_initialized()

    if _is_tensor_like(message):
        message = _format_tensor(message)

    if not isinstance(message, str):
        message = str(message)

    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()

    entry = {
        "type": "log",
        "node": node_id,
        "message": message,
        "step": step,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].logs.append(entry)

    for backend in state.backends:
        try:
            backend.on_log(node_id or "", message, timestamp)
        except Exception:
            pass

    state._send_to_client(entry)

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
    _ensure_initialized()
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

    state._send_to_client(entry)

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_image(image: Any, *, name: Optional[str] = None, step: Optional[int] = None) -> None:
    """Log an image (PIL, numpy array, or torch tensor).

    Args:
        name: The image name/label.
        image: The image data.
        step: Optional step counter.
    """
    _ensure_initialized()
    from graphbook.beta.logging.serializers import serialize_image

    import base64

    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()
    image_bytes = serialize_image(image)

    entry = {
        "type": "image",
        "node": node_id,
        "name": name,
        "data": base64.b64encode(image_bytes).decode("ascii"),
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

    state._send_to_client(entry)

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def log_audio(audio: Any, sr: int = 16000, *, name: Optional[str] = None, step: Optional[int] = None) -> None:
    """Log audio data.

    Args:
        name: The audio clip name.
        audio: Audio data as numpy array.
        sr: Sample rate.
    """
    _ensure_initialized()
    from graphbook.beta.logging.serializers import serialize_audio

    import base64

    state = get_state()
    node_id = _current_node.get()
    timestamp = time.time()
    audio_bytes = serialize_audio(audio, sr)

    entry = {
        "type": "audio",
        "node": node_id,
        "name": name,
        "data": base64.b64encode(audio_bytes).decode("ascii"),
        "sr": sr,
        "step": step,
        "timestamp": timestamp,
    }

    if node_id and node_id in state.nodes:
        state.nodes[node_id].audio.append({"name": name, "step": step, "sr": sr, "timestamp": timestamp})

    for backend in state.backends:
        try:
            backend.on_audio(node_id or "", name, audio_bytes, sr)
        except Exception:
            pass

    state._send_to_client(entry)

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
    _ensure_initialized()
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

    state._send_to_client(entry)

    if state._queue is not None:
        try:
            state._queue.put_event(entry)
        except Exception:
            pass


def md(description: str) -> None:
    """Set or append to the workflow-level description.

    This is distinct from node-level docstrings — it describes the overall workflow.

    Args:
        description: Markdown description of the workflow.
    """
    _ensure_initialized()
    state = get_state()
    if state.workflow_description is None:
        state.workflow_description = description
    else:
        state.workflow_description += "\n\n" + description
    state._send_to_client({
        "type": "description",
        "data": {"description": description},
    })

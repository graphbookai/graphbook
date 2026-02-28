"""Serializers for various data types (images, audio, tensors)."""

from __future__ import annotations

import io
from typing import Any


def serialize_image(image: Any) -> bytes:
    """Serialize an image to PNG bytes.

    Supports: PIL.Image, numpy array, torch tensor.

    Args:
        image: The image to serialize.

    Returns:
        PNG-encoded bytes.
    """
    # PIL Image
    try:
        from PIL import Image
        if isinstance(image, Image.Image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return buf.getvalue()
    except ImportError:
        pass

    # Torch tensor
    try:
        import torch
        if isinstance(image, torch.Tensor):
            import numpy as np
            arr = image.detach().cpu().numpy()
            return _numpy_to_png(arr)
    except ImportError:
        pass

    # Numpy array
    try:
        import numpy as np
        if isinstance(image, np.ndarray):
            return _numpy_to_png(image)
    except ImportError:
        pass

    raise TypeError(f"Cannot serialize image of type {type(image).__name__}")


def _numpy_to_png(arr: Any) -> bytes:
    """Convert a numpy array to PNG bytes."""
    import numpy as np
    from PIL import Image

    if arr.ndim == 3 and arr.shape[0] in (1, 3, 4):
        # CHW -> HWC
        arr = np.transpose(arr, (1, 2, 0))

    if arr.dtype == np.float32 or arr.dtype == np.float64:
        arr = (arr * 255).clip(0, 255).astype(np.uint8)

    if arr.ndim == 3 and arr.shape[2] == 1:
        arr = arr.squeeze(2)

    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def serialize_audio(audio: Any, sr: int = 16000) -> bytes:
    """Serialize audio to WAV bytes.

    Args:
        audio: Audio data as numpy array.
        sr: Sample rate.

    Returns:
        WAV-encoded bytes.
    """
    import numpy as np
    import struct
    import wave

    if not isinstance(audio, np.ndarray):
        audio = np.array(audio, dtype=np.float32)

    if audio.dtype in (np.float32, np.float64):
        audio = (audio * 32767).clip(-32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    channels = 1 if audio.ndim == 1 else audio.shape[1]

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())

    return buf.getvalue()

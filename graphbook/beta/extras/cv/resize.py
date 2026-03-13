"""Image resize operations."""

from __future__ import annotations

from typing import Optional, Tuple, Union

import numpy as np

from graphbook.beta.core.decorators import fn


@fn()
def resize(
    image: np.ndarray,
    size: Union[int, Tuple[int, int]] = 224,
    interpolation: str = "bilinear",
) -> np.ndarray:
    """Resize an image to the target size.

    Supports various interpolation modes. Works with numpy arrays (HWC or HW format).

    Args:
        image: Input image as numpy array.
        size: Target size. If int, resizes shortest edge. If tuple, (height, width).
        interpolation: Interpolation mode: 'nearest', 'bilinear', 'bicubic', 'area'.

    Returns:
        Resized image as numpy array.
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python is required for resize. Install with: pip install graphbook[cv]")

    interp_map = {
        "nearest": cv2.INTER_NEAREST,
        "bilinear": cv2.INTER_LINEAR,
        "bicubic": cv2.INTER_CUBIC,
        "area": cv2.INTER_AREA,
        "lanczos": cv2.INTER_LANCZOS4,
    }

    interp = interp_map.get(interpolation, cv2.INTER_LINEAR)

    if isinstance(size, int):
        h, w = image.shape[:2]
        if h < w:
            new_h = size
            new_w = int(w * size / h)
        else:
            new_w = size
            new_h = int(h * size / w)
        target_size = (new_w, new_h)
    else:
        target_size = (size[1], size[0])  # cv2 uses (width, height)

    return cv2.resize(image, target_size, interpolation=interp)

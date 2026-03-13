"""Image augmentation operations."""

from __future__ import annotations

import random
from typing import Optional, Tuple

import numpy as np

from graphbook.beta.core.decorators import fn


@fn()
def augment(
    image: np.ndarray,
    hflip: bool = False,
    vflip: bool = False,
    brightness: float = 0.0,
    contrast: float = 0.0,
    rotation: float = 0.0,
    crop: Optional[Tuple[int, int, int, int]] = None,
    random_hflip: float = 0.0,
    random_vflip: float = 0.0,
) -> np.ndarray:
    """Apply augmentation transforms to an image.

    Args:
        image: Input image as numpy array (HWC format).
        hflip: Apply horizontal flip.
        vflip: Apply vertical flip.
        brightness: Brightness adjustment factor (-1.0 to 1.0). 0 means no change.
        contrast: Contrast adjustment factor (-1.0 to 1.0). 0 means no change.
        rotation: Rotation angle in degrees.
        crop: Crop region as (x, y, width, height).
        random_hflip: Probability of random horizontal flip (0.0 to 1.0).
        random_vflip: Probability of random vertical flip (0.0 to 1.0).

    Returns:
        Augmented image as numpy array.
    """
    result = image.copy()

    # Horizontal flip
    if hflip or (random_hflip > 0 and random.random() < random_hflip):
        result = np.flip(result, axis=1).copy()

    # Vertical flip
    if vflip or (random_vflip > 0 and random.random() < random_vflip):
        result = np.flip(result, axis=0).copy()

    # Brightness
    if brightness != 0.0:
        result = np.clip(result.astype(np.float32) + brightness * 255, 0, 255).astype(np.uint8)

    # Contrast
    if contrast != 0.0:
        mean = result.mean()
        factor = 1.0 + contrast
        result = np.clip((result.astype(np.float32) - mean) * factor + mean, 0, 255).astype(np.uint8)

    # Rotation
    if rotation != 0.0:
        try:
            import cv2
            h, w = result.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
            result = cv2.warpAffine(result, matrix, (w, h))
        except ImportError:
            pass  # Skip rotation without opencv

    # Crop
    if crop is not None:
        x, y, cw, ch = crop
        result = result[y:y + ch, x:x + cw]

    return result

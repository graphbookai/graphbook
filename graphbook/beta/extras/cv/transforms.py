"""Common image transform functions."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

import numpy as np

from graphbook.beta.core.decorators import fn


@fn()
def normalize(
    image: np.ndarray,
    mean: Sequence[float] = (0.485, 0.456, 0.406),
    std: Sequence[float] = (0.229, 0.224, 0.225),
) -> np.ndarray:
    """Normalize an image with channel-wise mean and standard deviation.

    Converts to float32 [0,1] range first if needed, then applies normalization.

    Args:
        image: Input image as numpy array (HWC format).
        mean: Per-channel mean values.
        std: Per-channel standard deviation values.

    Returns:
        Normalized image as float32 numpy array.
    """
    result = image.astype(np.float32)
    if result.max() > 1.0:
        result = result / 255.0

    mean_arr = np.array(mean, dtype=np.float32)
    std_arr = np.array(std, dtype=np.float32)

    if result.ndim == 3:
        result = (result - mean_arr) / std_arr
    else:
        result = (result - mean_arr[0]) / std_arr[0]

    return result


@fn()
def to_tensor(image: np.ndarray) -> "Any":
    """Convert a numpy image to a PyTorch tensor.

    Converts HWC format to CHW format and ensures float32 dtype.

    Args:
        image: Input image as numpy array (HWC or HW format).

    Returns:
        PyTorch tensor in CHW format.
    """
    try:
        import torch
    except ImportError:
        raise ImportError("torch is required for to_tensor. Install with: pip install graphbook[cv]")

    if image.dtype == np.uint8:
        image = image.astype(np.float32) / 255.0

    if image.ndim == 3:
        # HWC -> CHW
        image = np.transpose(image, (2, 0, 1))
    elif image.ndim == 2:
        # HW -> 1HW
        image = image[np.newaxis, ...]

    return torch.from_numpy(image.copy())


@fn()
def detect_edges(
    image: np.ndarray,
    method: str = "canny",
    threshold1: float = 100.0,
    threshold2: float = 200.0,
    ksize: int = 3,
) -> np.ndarray:
    """Detect edges in an image.

    Args:
        image: Input image as numpy array.
        method: Edge detection method: 'canny' or 'sobel'.
        threshold1: First threshold for Canny (or ksize for Sobel).
        threshold2: Second threshold for Canny.
        ksize: Kernel size for Sobel.

    Returns:
        Edge map as numpy array.
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python is required for detect_edges. Install with: pip install graphbook[cv]")

    # Convert to grayscale if needed
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    if method == "canny":
        return cv2.Canny(gray, threshold1, threshold2)
    elif method == "sobel":
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)
        return np.sqrt(sobel_x**2 + sobel_y**2).astype(np.uint8)
    else:
        raise ValueError(f"Unknown edge detection method: {method}")


@fn()
def draw_boxes(
    image: np.ndarray,
    boxes: list,
    labels: Optional[list[str]] = None,
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw bounding boxes on an image.

    Args:
        image: Input image as numpy array.
        boxes: List of boxes as [x1, y1, x2, y2] or [(x1,y1,x2,y2),...].
        labels: Optional labels for each box.
        color: Box color as (B, G, R) tuple.
        thickness: Line thickness.

    Returns:
        Image with drawn boxes.
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python is required for draw_boxes. Install with: pip install graphbook[cv]")

    result = image.copy()
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = [int(c) for c in box]
        cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)
        if labels and i < len(labels):
            cv2.putText(result, labels[i], (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    return result


@fn()
def color_convert(
    image: np.ndarray,
    conversion: str = "bgr2rgb",
) -> np.ndarray:
    """Convert image color space.

    Args:
        image: Input image as numpy array.
        conversion: Color conversion. Options: 'bgr2rgb', 'rgb2bgr', 'bgr2gray',
                   'rgb2gray', 'bgr2hsv', 'hsv2bgr', 'rgb2hsv', 'hsv2rgb'.

    Returns:
        Color-converted image.
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python is required for color_convert. Install with: pip install graphbook[cv]")

    conversions = {
        "bgr2rgb": cv2.COLOR_BGR2RGB,
        "rgb2bgr": cv2.COLOR_RGB2BGR,
        "bgr2gray": cv2.COLOR_BGR2GRAY,
        "rgb2gray": cv2.COLOR_RGB2GRAY,
        "gray2bgr": cv2.COLOR_GRAY2BGR,
        "gray2rgb": cv2.COLOR_GRAY2RGB,
        "bgr2hsv": cv2.COLOR_BGR2HSV,
        "hsv2bgr": cv2.COLOR_HSV2BGR,
        "rgb2hsv": cv2.COLOR_RGB2HSV,
        "hsv2rgb": cv2.COLOR_HSV2RGB,
    }

    code = conversions.get(conversion.lower())
    if code is None:
        raise ValueError(f"Unknown conversion: {conversion}. Options: {list(conversions.keys())}")

    return cv2.cvtColor(image, code)

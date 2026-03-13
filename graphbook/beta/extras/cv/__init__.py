"""Computer vision extras for graphbook beta.

Install with: pip install graphbook[cv]

Provides pre-built @fn decorated functions for common CV operations.
"""

from graphbook.beta.extras.cv.resize import resize
from graphbook.beta.extras.cv.augment import augment
from graphbook.beta.extras.cv.transforms import normalize, to_tensor, color_convert, detect_edges, draw_boxes

__all__ = [
    "resize",
    "augment",
    "normalize",
    "to_tensor",
    "color_convert",
    "detect_edges",
    "draw_boxes",
]

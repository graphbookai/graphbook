"""3-Stage Image Processing Pipeline

Processes multiple images through 3 stages: Create, Warm Tint, Sharpen.
Step increments per image (not per stage), so scrubbing through steps
shows each image's full progression.

Stages per image:
  1. Create — Generate a colorful gradient
  2. Warm Tint — Boost reds, reduce blues
  3. Sharpen — Sharpen + contrast boost
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import graphbook.beta as gb


gb.md("# 3-Stage Image Pipeline\nCreate → Warm Tint → Sharpen (×500 images)")


def _make_gradient(index: int, size: int = 128) -> Image.Image:
    """Generate a colorful gradient image that varies by index."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    freq = 1 + index * 0.7
    for y in range(size):
        for x in range(size):
            arr[y, x, 0] = int(127 + 127 * np.sin(2 * np.pi * freq * x / size))
            arr[y, x, 1] = int(127 + 127 * np.sin(2 * np.pi * freq * y / size + index))
            arr[y, x, 2] = int(127 + 127 * np.cos(2 * np.pi * freq * (x + y) / size))
    return Image.fromarray(arr)


@gb.fn()
def create_images(num_images: int = 500, size: int = 128) -> list[Image.Image]:
    """Generate base gradient images."""
    images = []
    for i in range(num_images):
        img = _make_gradient(i, size)
        gb.log(f"Created gradient image {i}", step=i)
        gb.log_image(img, name="created", step=i)
        images.append(img)
    return images


@gb.fn()
def warm_tint(images: list[Image.Image]) -> list[Image.Image]:
    """Apply a warm tint: boost reds, reduce blues."""
    result = []
    for i, img in enumerate(images):
        arr = np.array(img, dtype=np.float32)
        arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.3, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.6, 0, 255)
        out = Image.fromarray(arr.astype(np.uint8))
        gb.log(f"Applied warm tint to image {i}", step=i)
        gb.log_image(out, name="warm_tint", step=i)
        result.append(out)
    return result


@gb.fn()
def sharpen(images: list[Image.Image]) -> list[Image.Image]:
    """Sharpen and boost contrast."""
    result = []
    for i, img in enumerate(images):
        sharpened = img.filter(ImageFilter.SHARPEN)
        out = ImageEnhance.Contrast(sharpened).enhance(1.5)
        gb.log(f"Sharpened image {i}", step=i)
        gb.log_image(out, name="sharpened", step=i)
        result.append(out)
    return result


@gb.fn()
def run_pipeline() -> list[Image.Image]:
    """Run all 3 stages across multiple images."""
    images = create_images()
    images = warm_tint(images)
    images = sharpen(images)
    gb.log("Pipeline complete")
    return images


def main():
    result = run_pipeline()
    print(f"Processed {len(result)} images through 3 stages")


if __name__ == "__main__":
    main()

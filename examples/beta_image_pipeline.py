"""Example 6: Image Processing Pipeline with log_image()

Demonstrates:
- @gb.fn() for registering pipeline steps
- gb.log_image(img, step=i) for logging images with step indices
- gb.log_cfg() for logging transform configuration
- gb.log_metric() for tracking image statistics
- Processing a batch of 10 images through a series of transforms
"""

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import graphbook.beta as gb


gb.md("""
# Image Processing Pipeline

Generates 10 synthetic images and processes each through a series of
transforms: grayscale conversion, Gaussian blur, contrast enhancement,
and edge detection. Each stage logs its output images with `gb.log_image()`.
""")


def _make_synthetic_image(index: int, size: int = 128) -> Image.Image:
    """Generate a colorful synthetic image based on the index."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    freq = 1 + index * 0.5
    for y in range(size):
        for x in range(size):
            arr[y, x, 0] = int(127 + 127 * np.sin(2 * np.pi * freq * x / size))
            arr[y, x, 1] = int(127 + 127 * np.sin(2 * np.pi * freq * y / size + index))
            arr[y, x, 2] = int(127 + 127 * np.cos(2 * np.pi * freq * (x + y) / size))
    return Image.fromarray(arr)


@gb.fn()
def generate_images(num_images: int = 10, size: int = 128) -> list[Image.Image]:
    """Generate a batch of synthetic test images."""
    gb.log_cfg({"num_images": num_images, "size": size})
    images = []
    for i in range(num_images):
        img = _make_synthetic_image(i, size)
        gb.log_image(img, name="generated", step=i)
        images.append(img)
    gb.log(f"Generated {num_images} images at {size}x{size}")
    return images


@gb.fn()
def to_grayscale(images: list[Image.Image]) -> list[Image.Image]:
    """Convert all images to grayscale."""
    gb.log_cfg({"mode": "L"})
    result = []
    for i, img in enumerate(images):
        gray = img.convert("L").convert("RGB")
        gb.log_image(gray, name="grayscale", step=i)
        result.append(gray)
    gb.log(f"Converted {len(images)} images to grayscale")
    return result


@gb.fn()
def apply_blur(images: list[Image.Image], radius: float = 2.0) -> list[Image.Image]:
    """Apply Gaussian blur to each image."""
    gb.log_cfg({"blur_radius": radius})
    result = []
    for i, img in enumerate(images):
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        gb.log_image(blurred, name="blurred", step=i)
        result.append(blurred)
    gb.log(f"Applied Gaussian blur (radius={radius}) to {len(images)} images")
    return result


@gb.fn()
def enhance_contrast(images: list[Image.Image], factor: float = 1.8) -> list[Image.Image]:
    """Enhance contrast of each image."""
    gb.log_cfg({"contrast_factor": factor})
    result = []
    for i, img in enumerate(images):
        enhanced = ImageEnhance.Contrast(img).enhance(factor)
        gb.log_image(enhanced, name="contrast_enhanced", step=i)
        result.append(enhanced)
    gb.log(f"Enhanced contrast (factor={factor}) on {len(images)} images")
    return result


@gb.fn()
def detect_edges(images: list[Image.Image]) -> list[Image.Image]:
    """Detect edges in each image using a Laplacian filter."""
    gb.log_cfg({"method": "FIND_EDGES"})
    result = []
    for i, img in enumerate(images):
        edges = img.filter(ImageFilter.FIND_EDGES)
        gb.log_image(edges, name="edges", step=i)

        arr = np.array(edges)
        mean_intensity = float(arr.mean())
        gb.log_metric("edge_intensity", mean_intensity, step=i)
        result.append(edges)
    gb.log(f"Detected edges in {len(images)} images")
    return result


@gb.fn()
def compute_stats(images: list[Image.Image]) -> dict:
    """Compute per-image brightness statistics."""
    stats = []
    for i, img in enumerate(images):
        arr = np.array(img).astype(np.float32)
        brightness = float(arr.mean())
        gb.log_metric("brightness", brightness, step=i)
        stats.append({"index": i, "brightness": brightness})
    avg = sum(s["brightness"] for s in stats) / len(stats)
    gb.log(f"Average brightness across {len(images)} images: {avg:.1f}")
    return {"per_image": stats, "average_brightness": avg}


@gb.fn()
def run_pipeline() -> dict:
    """Run the full image processing pipeline."""
    images = generate_images()
    gray = to_grayscale(images)
    blurred = apply_blur(gray)
    enhanced = enhance_contrast(blurred)
    edges = detect_edges(enhanced)
    stats = compute_stats(edges)
    return stats


def main():
    result = run_pipeline()
    print(f"\nProcessed {len(result['per_image'])} images")
    print(f"Average edge brightness: {result['average_brightness']:.1f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Example of using the graphbook logging system.

This example demonstrates how to use the graphbook Logger to log outputs,
images, and logs for visualization in the graphbook UI.

To run this example:
    python examples/logging_example.py

To view the logs:
    python -m graphbook.core.cli view logs/example.log
"""

import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the graphbook logging system
from graphbook.logging import DAGLogger

# Create a logger
logger = DAGLogger("example", "logs")

# Create a simple graph with nodes
node1_id = "1"
node2_id = "2"
node3_id = "3"

# Register nodes in the graph
node1 = logger.node(node1_id, "Image Generator", "Generates images")
node2 = logger.node(node2_id, "Image Processor", "Processes images", [node1_id])
node3 = logger.node(node3_id, "Output Formatter", "Formats output", [node2_id])

# Log messages
node1.log_message("Starting image generation", "info")
node2.log_message("Waiting for images to process", "info")
node3.log_message("Ready to format output", "info")

# Create and log some images
for i in range(5):
    # Create a simple colored image
    img = Image.new("RGB", (300, 200), color=(i * 50, 100, 150))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), f"Image {i+1}", fill=(255, 255, 255))

    # Log the image from the first node
    node1.log_message(f"Generated image {i+1}", "info")
    node1.log_image(img)

    # Simulate processing in the second node
    time.sleep(0.5)
    node2.log_message(f"Processing image {i+1}", "info")

    # Create a processed image by adding a border
    processed_img = Image.new("RGB", (320, 220), color=(255, 0, 0))
    processed_img.paste(img, (10, 10))
    node2.log_image(processed_img)

    # Log structured output from the third node
    time.sleep(0.5)
    node3.log_message(f"Formatting output for image {i+1}", "info")
    node3.log_output(
        {
            "image_id": i + 1,
            "dimensions": img.size,
            "processed": True,
            "timestamp": time.time(),
        }
    )

# Log a final message
node1.log_message("Image generation complete", "info")
node2.log_message("Image processing complete", "info")
node3.log_message("Output formatting complete", "info")

print("Log file created at:", logger.filepath)
print("To view the logs, run: python -m graphbook.core.cli view", logger.filepath)

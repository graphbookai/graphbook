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

import os
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the graphbook logging system
from graphbook.logging import create_logger

# Create a logger
logger = create_logger("example", "logs")

# Create a simple graph with nodes
node1_id = "1"
node2_id = "2"
node3_id = "3"

# Register nodes in the graph
logger.node(node1_id, "Image Generator", "Generates images")
logger.node(node2_id, "Image Processor", "Processes images", [node1_id])
logger.node(node3_id, "Output Formatter", "Formats output", [node2_id])

# Log messages
logger.log_message(node1_id, "Starting image generation", "info")
logger.log_message(node2_id, "Waiting for images to process", "info")
logger.log_message(node3_id, "Ready to format output", "info")

# Create and log some images
for i in range(5):
    # Create a simple colored image
    img = Image.new('RGB', (300, 200), color=(i*50, 100, 150))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), f"Image {i+1}", fill=(255, 255, 255))
    
    # Log the image from the first node
    logger.log_message(node1_id, f"Generated image {i+1}", "info")
    logger.log_image(node1_id, img)
    
    # Simulate processing in the second node
    time.sleep(0.5)
    logger.log_message(node2_id, f"Processing image {i+1}", "info")
    
    # Create a processed image by adding a border
    processed_img = Image.new('RGB', (320, 220), color=(255, 0, 0))
    processed_img.paste(img, (10, 10))
    logger.log_image(node2_id, processed_img)
    
    # Log structured output from the third node
    time.sleep(0.5)
    logger.log_message(node3_id, f"Formatting output for image {i+1}", "info")
    logger.log_output(node3_id, {
        "image_id": i+1,
        "dimensions": img.size,
        "processed": True,
        "timestamp": time.time()
    })

# Log a final message
logger.log_message(node1_id, "Image generation complete", "info")
logger.log_message(node2_id, "Image processing complete", "info")
logger.log_message(node3_id, "Output formatting complete", "info")

print("Log file created at:", logger.filepath)
print("To view the logs, run: python -m graphbook.core.cli view", logger.filepath)
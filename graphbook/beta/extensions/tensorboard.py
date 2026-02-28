"""TensorBoard logging backend extension for graphbook beta.

Usage:
    from graphbook.beta.extensions.tensorboard import TensorboardBackend
    gb.init(backends=[TensorboardBackend(log_dir="runs/exp1")])
"""

from __future__ import annotations

from typing import Any, Optional


class TensorboardBackend:
    """Logging backend that writes to TensorBoard.

    Requires tensorboard to be installed:
        pip install graphbook[tensorboard]
    """

    def __init__(self, log_dir: str = "runs", comment: str = "") -> None:
        """Initialize the TensorBoard backend.

        Args:
            log_dir: Directory for TensorBoard log files.
            comment: Comment to append to the log directory name.
        """
        try:
            from torch.utils.tensorboard import SummaryWriter
            self._writer = SummaryWriter(log_dir=log_dir, comment=comment)
        except ImportError:
            raise ImportError(
                "tensorboard is required for TensorboardBackend. "
                "Install with: pip install graphbook[tensorboard]"
            )
        self._step_counters: dict[str, int] = {}

    def on_log(self, node: str, message: str, timestamp: float) -> None:
        """Log a text message to TensorBoard."""
        self._writer.add_text(f"{node}/logs", message, self._get_step(node))

    def on_metric(self, node: str, name: str, value: float, step: int) -> None:
        """Log a scalar metric to TensorBoard."""
        self._writer.add_scalar(f"{node}/{name}", value, step)

    def on_image(self, node: str, name: str, image_bytes: bytes, step: int) -> None:
        """Log an image to TensorBoard."""
        import io
        from PIL import Image
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]  # Add channel dim
        elif arr.ndim == 3:
            arr = np.transpose(arr, (2, 0, 1))  # HWC -> CHW
        self._writer.add_image(f"{node}/{name}", arr, step)

    def on_audio(self, node: str, name: str, audio_bytes: bytes, sr: int) -> None:
        """Log audio to TensorBoard."""
        pass  # TensorBoard audio requires specific format handling

    def on_node_start(self, node: str, params: dict) -> None:
        """Record node execution start."""
        pass

    def on_node_end(self, node: str, duration: float) -> None:
        """Record node execution end with duration."""
        self._writer.add_scalar(f"{node}/duration", duration, self._get_step(node))

    def flush(self) -> None:
        """Flush pending writes to disk."""
        self._writer.flush()

    def close(self) -> None:
        """Close the TensorBoard writer."""
        self._writer.close()

    def _get_step(self, node: str) -> int:
        """Get and increment the step counter for a node."""
        step = self._step_counters.get(node, 0)
        self._step_counters[node] = step + 1
        return step

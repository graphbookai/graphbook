"""MLflow logging backend extension for graphbook beta.

Usage:
    from graphbook.beta.extensions.mlflow import MLflowBackend
    gb.init(backends=[MLflowBackend(experiment_name="my_exp")])
"""

from __future__ import annotations

from typing import Any, Optional


class MLflowBackend:
    """Logging backend that writes to MLflow.

    Requires mlflow to be installed:
        pip install graphbook[mlflow]
    """

    def __init__(
        self,
        experiment_name: str = "graphbook",
        run_name: Optional[str] = None,
        tracking_uri: Optional[str] = None,
    ) -> None:
        """Initialize the MLflow backend.

        Args:
            experiment_name: MLflow experiment name.
            run_name: Optional run name.
            tracking_uri: Optional MLflow tracking server URI.
        """
        try:
            import mlflow
        except ImportError:
            raise ImportError(
                "mlflow is required for MLflowBackend. "
                "Install with: pip install graphbook[mlflow]"
            )

        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        mlflow.set_experiment(experiment_name)
        self._run = mlflow.start_run(run_name=run_name)
        self._mlflow = mlflow

    def on_log(self, node: str, message: str, timestamp: float) -> None:
        """Log a text message as MLflow tag."""
        pass  # MLflow doesn't have a great text log API

    def on_metric(self, node: str, name: str, value: float, step: int) -> None:
        """Log a scalar metric to MLflow."""
        self._mlflow.log_metric(f"{node}.{name}", value, step=step)

    def on_image(self, node: str, name: str, image_bytes: bytes, step: int) -> None:
        """Log an image as MLflow artifact."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            f.flush()
            self._mlflow.log_artifact(f.name, f"{node}/images")
            os.unlink(f.name)

    def on_audio(self, node: str, name: str, audio_bytes: bytes, sr: int) -> None:
        """Log audio as MLflow artifact."""
        pass

    def on_node_start(self, node: str, params: dict) -> None:
        """Log node parameters to MLflow."""
        for k, v in params.items():
            try:
                self._mlflow.log_param(f"{node}.{k}", v)
            except Exception:
                pass

    def on_node_end(self, node: str, duration: float) -> None:
        """Log node duration to MLflow."""
        self._mlflow.log_metric(f"{node}.duration", duration)

    def flush(self) -> None:
        """Flush (no-op for MLflow)."""
        pass

    def close(self) -> None:
        """End the MLflow run."""
        self._mlflow.end_run()

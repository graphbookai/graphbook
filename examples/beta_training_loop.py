"""Example 2: ML Training Loop with Metrics and Inspection

Demonstrates:
- gb.log_metric() for tracking loss, accuracy over steps
- gb.log_image() for logging generated images
- @gb.fn() on training functions
- Metric history accessible via the state API
- Exception capture and enrichment
"""

import numpy as np
from PIL import Image
import graphbook.beta as gb


gb.md("A simulated ML training loop that trains a classifier and logs metrics, inspections, and sample images.")


@gb.fn()
def create_dataset(num_samples: int = 100, num_features: int = 10) -> dict:
    """Create a synthetic classification dataset with random features and labels."""
    X = np.random.randn(num_samples, num_features).astype(np.float32)
    y = (np.random.rand(num_samples) > 0.5).astype(np.int64)
    gb.log(f"Created dataset: {num_samples} samples, {num_features} features")
    return {"X": X, "y": y}


@gb.fn()
def create_model(input_dim: int = 10, hidden_dim: int = 32) -> dict:
    """Initialize model weights with random values."""
    weights = {
        "W1": np.random.randn(input_dim, hidden_dim).astype(np.float32) * 0.01,
        "b1": np.zeros(hidden_dim, dtype=np.float32),
        "W2": np.random.randn(hidden_dim, 1).astype(np.float32) * 0.01,
        "b2": np.zeros(1, dtype=np.float32),
    }
    gb.log(f"Created model: {input_dim} → {hidden_dim} → 1")
    return weights


@gb.fn(pausable=True)
def train_step(model: dict, batch_X: np.ndarray, batch_y: np.ndarray, lr: float = 0.01) -> tuple:
    """Run a single forward pass and compute binary cross-entropy loss."""
    # Forward pass (simplified)
    h = np.maximum(0, batch_X @ model["W1"] + model["b1"])  # ReLU
    logits = (h @ model["W2"] + model["b2"]).squeeze()

    # Sigmoid
    preds = 1.0 / (1.0 + np.exp(-np.clip(logits, -500, 500)))

    # Binary cross-entropy loss
    eps = 1e-7
    loss = -np.mean(batch_y * np.log(preds + eps) + (1 - batch_y) * np.log(1 - preds + eps))

    # Accuracy
    predicted_labels = (preds > 0.5).astype(np.int64)
    accuracy = np.mean(predicted_labels == batch_y)

    return float(loss), float(accuracy)


@gb.fn()
def generate_sample_image(epoch: int) -> np.ndarray:
    """Generate a sample visualization image showing training progress."""
    # Create a simple gradient image that changes with epoch
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    for i in range(64):
        for j in range(64):
            img[i, j, 0] = int((i / 64) * 255)                    # Red gradient
            img[i, j, 1] = int((j / 64) * 255)                    # Green gradient
            img[i, j, 2] = int(((epoch * 25) % 255))              # Blue varies by epoch
    return img


@gb.fn()
def train(dataset: dict, model: dict, epochs: int = 10, batch_size: int = 16) -> dict:
    """Train the model for multiple epochs with mini-batch gradient descent."""
    X, y = dataset["X"], dataset["y"]
    num_samples = len(X)
    history = {"loss": [], "accuracy": []}

    for epoch in gb.track(range(epochs), name="epochs"):
        epoch_losses = []
        epoch_accs = []

        # Mini-batch training
        indices = np.random.permutation(num_samples)
        for start in range(0, num_samples, batch_size):
            end = min(start + batch_size, num_samples)
            batch_idx = indices[start:end]
            batch_X = X[batch_idx]
            batch_y = y[batch_idx]

            loss, accuracy = train_step(model, batch_X, batch_y)
            epoch_losses.append(loss)
            epoch_accs.append(accuracy)

        # Log epoch-level metrics
        avg_loss = np.mean(epoch_losses)
        avg_acc = np.mean(epoch_accs)
        history["loss"].append(avg_loss)
        history["accuracy"].append(avg_acc)

        gb.log_metric("loss", float(avg_loss), step=epoch)
        gb.log_metric("accuracy", float(avg_acc), step=epoch)
        gb.log(f"Epoch {epoch}: loss={avg_loss:.4f}, accuracy={avg_acc:.4f}")

        # Log a sample image every 3 epochs
        if epoch % 3 == 0:
            sample_img = generate_sample_image(epoch)
            pil_img = Image.fromarray(sample_img)
            gb.log_image(pil_img, name=f"sample_epoch_{epoch}", step=epoch)
            gb.log(f"Logged sample image for epoch {epoch}")

    return history


@gb.fn()
def run_experiment() -> dict:
    """Top-level experiment runner that orchestrates dataset creation, model init, and training.

    This is the source node — calling create_dataset, create_model, and train
    from here creates the DAG edges automatically.
    """
    dataset = create_dataset(num_samples=200, num_features=10)
    model = create_model(input_dim=10, hidden_dim=32)
    history = train(dataset, model, epochs=10000, batch_size=32)
    return history


def main():
    """Run the training pipeline."""
    history = run_experiment()
    print(f"\nFinal loss: {history['loss'][-1]:.4f}")
    print(f"Final accuracy: {history['accuracy'][-1]:.4f}")


if __name__ == "__main__":
    main()

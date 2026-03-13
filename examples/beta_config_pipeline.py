"""Example 3: Data Processing Pipeline with Config Logging

Demonstrates:
- gb.log_cfg() for logging step configuration to the info tab
- @gb.fn() to register pipeline steps
- gb.log() for text and tensor-like object logging
- gb.log_text() for rich markdown logging
- Multiple source nodes and branching DAG
- Error capture with enriched tracebacks
- Full graph inspection via get_graph_dict()
"""

import time
import numpy as np
import graphbook.beta as gb


gb.md("""
# Data Processing Pipeline

This pipeline generates synthetic data, processes it through normalization
and filtering, then runs statistical analysis. Configuration is logged
via `gb.log_cfg()` — each step declares what it was configured with.
""")


@gb.fn()
def generate_data(num_samples: int = 100, noise_level: float = 0.2, seed: int = 0) -> np.ndarray:
    """Generate synthetic time-series data with configurable noise level."""
    gb.log_cfg({"num_samples": num_samples, "noise_level": noise_level, "seed": seed})
    np.random.seed(seed)
    t = np.linspace(0, 4 * np.pi, num_samples)
    signal = np.sin(t) + noise_level * np.random.randn(num_samples)
    gb.log(f"Generated {num_samples} samples with noise_level={noise_level}, seed={seed}")
    gb.log(signal)
    time.sleep(0.5)
    return signal


@gb.fn()
def generate_metadata(num_samples: int = 100, seed: int = 0) -> dict:
    """Generate metadata labels for each data sample."""
    gb.log_cfg({"num_samples": num_samples, "seed": seed})
    np.random.seed(seed + 1)
    labels = np.random.choice(["A", "B", "C"], size=num_samples)
    timestamps = np.arange(num_samples, dtype=np.float64)
    metadata = {"labels": labels, "timestamps": timestamps}
    gb.log(f"Generated metadata for {num_samples} samples")
    gb.log(labels)
    time.sleep(0.5)
    return metadata


@gb.fn()
def normalize_data(
    data: np.ndarray,
    method: str = "standard",
    clip_min: float = -5.0,
    clip_max: float = 5.0,
) -> np.ndarray:
    """Normalize data using the configured method and clip to range."""
    gb.log_cfg({"method": method, "clip_min": clip_min, "clip_max": clip_max})
    if method == "standard":
        mean, std = data.mean(), data.std()
        normalized = (data - mean) / (std + 1e-8)
        gb.log(f"Standard normalization: mean={mean:.4f}, std={std:.4f}")
    elif method == "minmax":
        dmin, dmax = data.min(), data.max()
        normalized = (data - dmin) / (dmax - dmin + 1e-8)
        gb.log(f"MinMax normalization: min={dmin:.4f}, max={dmax:.4f}")
    else:
        normalized = data
        gb.log(f"No normalization (unknown method: {method})")

    clipped = np.clip(normalized, clip_min, clip_max)
    gb.log(f"Clipped to [{clip_min}, {clip_max}]")
    gb.log(clipped)
    time.sleep(0.5)
    return clipped


@gb.fn()
def filter_by_label(data: np.ndarray, metadata: dict, label: str = "A") -> np.ndarray:
    """Filter data points to only include those matching a specific label."""
    mask = metadata["labels"] == label
    filtered = data[mask]
    gb.log(f"Filtered to label='{label}': {mask.sum()}/{len(data)} samples")
    gb.log(filtered)
    time.sleep(0.5)
    return filtered


@gb.fn()
def compute_statistics(
    data: np.ndarray,
    top_k: int = 10,
    threshold: float = 0.0,
) -> dict:
    """Compute descriptive statistics and find top-K values above threshold."""
    gb.log_cfg({"top_k": top_k, "threshold": threshold})
    stats = {
        "mean": float(data.mean()),
        "std": float(data.std()),
        "min": float(data.min()),
        "max": float(data.max()),
        "median": float(np.median(data)),
        "count": int(len(data)),
        "above_threshold": int(np.sum(data > threshold)),
    }

    # Find top-K values
    if len(data) >= top_k:
        top_indices = np.argsort(np.abs(data))[-top_k:]
        stats["top_k_values"] = data[top_indices].tolist()
    else:
        stats["top_k_values"] = sorted(data.tolist(), key=abs, reverse=True)

    gb.log(f"Statistics: mean={stats['mean']:.4f}, std={stats['std']:.4f}, "
           f"{stats['above_threshold']}/{stats['count']} above threshold={threshold}")

    # Log a rich text summary
    gb.log_text("stats_summary", f"""## Statistical Summary
- **Samples**: {stats['count']}
- **Mean**: {stats['mean']:.4f}
- **Std Dev**: {stats['std']:.4f}
- **Range**: [{stats['min']:.4f}, {stats['max']:.4f}]
- **Above threshold ({threshold})**: {stats['above_threshold']}
""")

    time.sleep(0.5)
    return stats


@gb.fn()
def generate_report(all_stats: dict, filtered_stats: dict) -> str:
    """Generate a final comparison report between full and filtered datasets."""
    report_lines = [
        "=" * 50,
        "ANALYSIS REPORT",
        "=" * 50,
        "",
        f"Full dataset:     mean={all_stats['mean']:.4f}, std={all_stats['std']:.4f}, n={all_stats['count']}",
        f"Filtered (label A): mean={filtered_stats['mean']:.4f}, std={filtered_stats['std']:.4f}, n={filtered_stats['count']}",
        "",
        f"Difference in mean: {abs(all_stats['mean'] - filtered_stats['mean']):.4f}",
        f"Top-K values (full): {[f'{v:.2f}' for v in all_stats['top_k_values'][:3]]}",
        f"Top-K values (filtered): {[f'{v:.2f}' for v in filtered_stats['top_k_values'][:3]]}",
    ]
    report = "\n".join(report_lines)
    gb.log(report)
    time.sleep(0.5)
    return report


@gb.fn()
def run_analysis() -> str:
    """Top-level analysis runner that orchestrates data generation, processing, and reporting.

    This is the source node. Calling other @fn functions from here creates
    DAG edges automatically: run_analysis -> generate_data, run_analysis -> normalize_data, etc.
    """
    # Data generation
    data = generate_data()
    metadata = generate_metadata()

    # Processing
    normalized = normalize_data(data)

    # Filtering
    filtered = filter_by_label(normalized, metadata, label="A")

    # Analysis — two calls to compute_statistics
    all_stats = compute_statistics(normalized)
    filtered_stats = compute_statistics(filtered)

    # Final report
    return generate_report(all_stats, filtered_stats)


def main():
    """Run the data processing pipeline."""
    report = run_analysis()
    print(report)

if __name__ == "__main__":
    main()

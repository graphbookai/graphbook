"""Example 3: Data Processing Pipeline with Config Injection

Demonstrates:
- gb.configure() for hydr8-style config injection
- @gb.step("config_key") to inject config values into function parameters
- gb.log_text() for rich markdown logging
- Multiple source nodes and branching DAG
- Error capture with enriched tracebacks
- Full graph inspection via get_graph_dict()
"""

import numpy as np

import graphbook.beta as gb
from graphbook.beta.core.state import get_state, SessionState
from graphbook.beta.core.dag import get_dag_summary, get_topology_order

# Reset state so the example is self-contained
SessionState.reset_singleton()

# Configuration for the pipeline
config = {
    "data": {
        "num_samples": 50,
        "noise_level": 0.1,
        "seed": 42,
    },
    "processing": {
        "method": "standard",
        "clip_min": -3.0,
        "clip_max": 3.0,
    },
    "analysis": {
        "top_k": 5,
        "threshold": 0.5,
    },
}

gb.configure(config)
gb.md("""
# Data Processing Pipeline

This pipeline generates synthetic data, processes it through normalization
and filtering, then runs statistical analysis. Configuration is injected
via `gb.configure()` — no hardcoded values in the processing functions.
""")


@gb.step("data")
def generate_data(num_samples: int = 100, noise_level: float = 0.2, seed: int = 0) -> np.ndarray:
    """Generate synthetic time-series data with configurable noise level."""
    np.random.seed(seed)
    t = np.linspace(0, 4 * np.pi, num_samples)
    signal = np.sin(t) + noise_level * np.random.randn(num_samples)
    gb.log(f"Generated {num_samples} samples with noise_level={noise_level}, seed={seed}")
    gb.inspect(signal, "raw_signal")
    return signal


@gb.step("data")
def generate_metadata(num_samples: int = 100, seed: int = 0) -> dict:
    """Generate metadata labels for each data sample."""
    np.random.seed(seed + 1)
    labels = np.random.choice(["A", "B", "C"], size=num_samples)
    timestamps = np.arange(num_samples, dtype=np.float64)
    metadata = {"labels": labels, "timestamps": timestamps}
    gb.log(f"Generated metadata for {num_samples} samples")
    gb.inspect(labels, "labels")
    return metadata


@gb.step("processing")
def normalize_data(
    data: np.ndarray,
    method: str = "standard",
    clip_min: float = -5.0,
    clip_max: float = 5.0,
) -> np.ndarray:
    """Normalize data using the configured method and clip to range."""
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
    gb.inspect(clipped, "normalized_data")
    return clipped


@gb.step()
def filter_by_label(data: np.ndarray, metadata: dict, label: str = "A") -> np.ndarray:
    """Filter data points to only include those matching a specific label."""
    mask = metadata["labels"] == label
    filtered = data[mask]
    gb.log(f"Filtered to label='{label}': {mask.sum()}/{len(data)} samples")
    gb.inspect(filtered, f"filtered_{label}")
    return filtered


@gb.step("analysis")
def compute_statistics(
    data: np.ndarray,
    top_k: int = 10,
    threshold: float = 0.0,
) -> dict:
    """Compute descriptive statistics and find top-K values above threshold."""
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

    return stats


@gb.step()
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
    return report


@gb.step()
def run_analysis() -> str:
    """Top-level analysis runner that orchestrates data generation, processing, and reporting.

    This is the source node. Calling other @step functions from here creates
    DAG edges automatically: run_analysis → generate_data, run_analysis → normalize_data, etc.
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

    # Print the report
    print(report)

    # Show pipeline structure
    print("\n" + "=" * 50)
    print("PIPELINE STRUCTURE")
    print("=" * 50)
    print(f"\nDAG: {get_dag_summary()}")
    print(f"Topological order: {get_topology_order()}")

    state = get_state()
    print(f"\nNodes ({len(state.nodes)}):")
    for nid, node in state.nodes.items():
        source_tag = " [SOURCE]" if node.is_source else ""
        config_tag = f" (config: {node.config_key})" if node.config_key else ""
        print(f"  {node.func_name}{source_tag}{config_tag}: "
              f"{node.exec_count}x, {len(node.logs)} logs")
        if node.params:
            print(f"    Injected params: {node.params}")

    print(f"\nEdges ({len(state.edges)}):")
    for edge in state.edges:
        src = edge.source.split(".")[-1]
        tgt = edge.target.split(".")[-1]
        print(f"  {src} → {tgt}")

    # Show workflow description
    print(f"\nWorkflow description set: {'Yes' if state.workflow_description else 'No'}")

    # Show graph dict (what MCP would return)
    graph = state.get_graph_dict()
    print(f"\nGraph dict: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    for node in graph["nodes"].values():
        print(f"Node {node['func_name']}: (execute count: {node['exec_count']}) (config: {node['config_key']})")

if __name__ == "__main__":
    main()

"""Example 5: Inspecting Graph State After Execution

Demonstrates how to query the graphbook state API after running a pipeline:
- DAG topology: get_dag_summary(), get_sources(), get_topology_order()
- Node details: exec_count, logs, metrics, errors, params
- Edge listing
- Serializable graph dict (what MCP tools return)
- Cycle detection via topological order gaps
- Workflow description

Run one of the other examples first (or run the small inline pipeline below),
then inspect the resulting state.
"""

import time

import graphbook.beta as gb
from graphbook.beta.core.state import get_state
from graphbook.beta.core.dag import get_dag_summary, get_sources, get_topology_order


# --- Small pipeline to generate some state ---

@gb.fn()
def load_data(path: str = "data.csv", limit: int = 100) -> list[dict]:
    """Load raw records from a data source."""
    records = [{"id": i, "value": i * 0.5} for i in range(limit)]
    gb.log(f"Loaded {len(records)} records from {path}")
    time.sleep(0.3)
    return records


@gb.fn()
def transform(records: list[dict]) -> list[dict]:
    """Normalize values and tag each record."""
    transformed = []
    for r in gb.track(records, name="transforming"):
        transformed.append({**r, "value": r["value"] / 50.0, "tagged": True})
    gb.log(f"Transformed {len(transformed)} records")
    gb.log_metric("record_count", float(len(transformed)))
    time.sleep(0.3)
    return transformed


@gb.fn()
def aggregate(records: list[dict]) -> dict:
    """Compute summary statistics over the transformed dataset."""
    values = [r["value"] for r in records]
    stats = {
        "count": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }
    gb.log(f"Aggregated: mean={stats['mean']:.4f}, count={stats['count']}")
    gb.log_metric("mean_value", stats["mean"])
    time.sleep(0.3)
    return stats


@gb.fn()
def run(path: str = "data.csv") -> dict:
    """Top-level runner: load → transform → aggregate."""
    records = load_data(path=path)
    transformed = transform(records)
    return aggregate(transformed)


# --- Configure and execute ---

gb.configure({"model": {"path": "data.csv", "limit": 50}})
gb.md("A minimal ETL pipeline used to demonstrate state inspection.")


def main():
    """Run the pipeline, then show every kind of state inspection."""
    result = run()

    state = get_state()

    # --- DAG topology ---
    print("=" * 60)
    print("DAG TOPOLOGY")
    print("=" * 60)
    print(f"  Summary:          {get_dag_summary()}")
    print(f"  Source nodes:     {get_sources()}")
    topo = get_topology_order()
    print(f"  Topological order ({len(topo)}): {topo}")

    # Cycle detection
    missing = set(state.nodes.keys()) - set(topo)
    if missing:
        names = [state.nodes[nid].func_name for nid in missing]
        print(f"  Cycle detected — nodes dropped from topo order: {names}")

    # --- Nodes ---
    print(f"\n{'=' * 60}")
    print("REGISTERED NODES")
    print("=" * 60)
    for node_id, node in state.nodes.items():
        source_tag = " [SOURCE]" if node.is_source else ""
        doc_preview = ""
        if node.docstring:
            doc_preview = node.docstring[:60] + ("..." if len(node.docstring) > 60 else "")
        print(f"\n  {node.func_name}{source_tag}")
        print(f"    exec_count: {node.exec_count}")
        print(f"    docstring:  {doc_preview!r}")
        print(f"    logs:       {len(node.logs)} entries")
        if node.params:
            print(f"    params:     {node.params}")
        if node.metrics:
            for metric_name, history in node.metrics.items():
                print(f"    metric '{metric_name}': {len(history)} points, latest={history[-1][1]:.4f}")
        if node.errors:
            print(f"    errors:     {len(node.errors)}")
            for err in node.errors:
                print(f"      [{err['type']}] {err['error']}")

    # --- Edges ---
    print(f"\n{'=' * 60}")
    print("EDGES")
    print("=" * 60)
    for edge in state.edges:
        src = edge.source.split(".")[-1]
        tgt = edge.target.split(".")[-1]
        print(f"  {src} → {tgt}")

    # --- Workflow description ---
    print(f"\n{'=' * 60}")
    print("WORKFLOW DESCRIPTION")
    print("=" * 60)
    if state.workflow_description:
        print(f"  {state.workflow_description.strip()}")
    else:
        print("  (none set)")

    # --- Serializable graph dict (what MCP tools return) ---
    print(f"\n{'=' * 60}")
    print("GRAPH DICT (serializable)")
    print("=" * 60)
    graph = state.get_graph_dict()
    print(f"  {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    for nid, node in graph["nodes"].items():
        print(f"  {node['func_name']}: exec_count={node['exec_count']}, "
              f"is_source={node['is_source']}")

    # --- Final result ---
    print(f"\n{'=' * 60}")
    print("PIPELINE RESULT")
    print("=" * 60)
    print(f"  {result}")


if __name__ == "__main__":
    main()

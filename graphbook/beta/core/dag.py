"""Runtime DAG builder with automatic source inference."""

from __future__ import annotations

from typing import Optional

from graphbook.beta.core.state import get_state


def add_edge(source: str, target: str) -> None:
    """Record a DAG edge from source to target node."""
    state = get_state()
    state.add_edge(source, target)


def get_sources() -> list[str]:
    """Return all source nodes (in-degree 0)."""
    state = get_state()
    return state.get_sources()


def get_topology_order() -> list[str]:
    """Return nodes in topological order using Kahn's algorithm."""
    state = get_state()
    in_degree: dict[str, int] = {nid: 0 for nid in state.nodes}
    adjacency: dict[str, list[str]] = {nid: [] for nid in state.nodes}

    for edge in state.edges:
        if edge.source in adjacency and edge.target in in_degree:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in adjacency.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result


def get_dag_summary() -> str:
    """Return a text summary of the DAG topology."""
    order = get_topology_order()
    if not order:
        return "No nodes registered"
    return " → ".join(order)

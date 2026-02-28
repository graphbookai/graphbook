"""Individual MCP tool implementations for graphbook beta."""

from __future__ import annotations

import time
from typing import Any, Optional


async def get_graph(server_url: str = "http://localhost:2048") -> dict[str, Any]:
    """Get the full DAG structure with nodes, edges, and status.

    Returns nodes with docstrings, source/non-source status, execution counts,
    and edges representing data flow.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{server_url}/graph", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # Fallback to in-process state
            from graphbook.beta.core.state import get_state
            return get_state().get_graph_dict()


async def get_node_status(name: str, server_url: str = "http://localhost:2048") -> dict[str, Any]:
    """Get detailed status for a specific node.

    Includes execution count, parameters, docstring, recent logs,
    errors, and source/non-source classification.

    Args:
        name: The node name/id.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{server_url}/nodes/{name}", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            from graphbook.beta.core.state import get_state
            state = get_state()
            node = state.nodes.get(name)
            if node is None:
                return {"error": f"Node '{name}' not found"}
            return {
                "name": node.name,
                "func_name": node.func_name,
                "docstring": node.docstring,
                "config_key": node.config_key,
                "exec_count": node.exec_count,
                "is_source": node.is_source,
                "params": node.params,
                "recent_logs": node.logs[-20:],
                "errors": node.errors,
                "progress": node.progress,
                "inspections": node.inspections,
            }


async def get_logs(
    node: Optional[str] = None,
    limit: int = 100,
    server_url: str = "http://localhost:2048",
) -> dict[str, Any]:
    """Get recent logs, optionally filtered by node.

    Args:
        node: Optional node name to filter by.
        limit: Maximum number of log entries to return.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            params = {"limit": limit}
            if node:
                params["node"] = node
            resp = await client.get(f"{server_url}/logs", params=params, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            from graphbook.beta.core.state import get_state
            state = get_state()
            all_logs = []
            for nid, n in state.nodes.items():
                if node and nid != node:
                    continue
                all_logs.extend(n.logs)
            all_logs.sort(key=lambda x: x.get("timestamp", 0))
            return {"logs": all_logs[-limit:]}


async def get_metrics(
    node: str,
    name: Optional[str] = None,
    server_url: str = "http://localhost:2048",
) -> dict[str, Any]:
    """Get metric history for a node.

    Args:
        node: The node name.
        name: Optional metric name to filter by.
    """
    from graphbook.beta.core.state import get_state
    state = get_state()
    node_info = state.nodes.get(node)
    if node_info is None:
        return {"error": f"Node '{node}' not found"}

    metrics = node_info.metrics
    if name:
        if name in metrics:
            return {"node": node, "metrics": {name: [{"step": s, "value": v} for s, v in metrics[name]]}}
        return {"error": f"Metric '{name}' not found for node '{node}'"}

    return {
        "node": node,
        "metrics": {
            k: [{"step": s, "value": v} for s, v in entries]
            for k, entries in metrics.items()
        },
    }


async def get_errors(server_url: str = "http://localhost:2048") -> dict[str, Any]:
    """Get all exceptions/errors across the pipeline.

    Returns tracebacks enriched with node context.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{server_url}/errors", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            from graphbook.beta.core.state import get_state
            state = get_state()
            all_errors = []
            for nid, n in state.nodes.items():
                all_errors.extend(n.errors)
            return {"errors": all_errors}


async def get_description(server_url: str = "http://localhost:2048") -> dict[str, Any]:
    """Get workflow description from gb.md() calls and all node docstrings.

    Returns:
        Workflow-level description plus all node docstrings.
    """
    from graphbook.beta.core.state import get_state
    state = get_state()
    node_docs = {
        nid: n.docstring
        for nid, n in state.nodes.items()
        if n.docstring
    }
    return {
        "workflow_description": state.workflow_description,
        "node_descriptions": node_docs,
    }


async def inspect_object(
    name: str,
    node: Optional[str] = None,
    server_url: str = "http://localhost:2048",
) -> dict[str, Any]:
    """Get the last inspection result for a named object.

    Args:
        name: The inspection name.
        node: Optional node to search in.
    """
    from graphbook.beta.core.state import get_state
    state = get_state()

    if node:
        node_info = state.nodes.get(node)
        if node_info and name in node_info.inspections:
            return {"node": node, "inspection": node_info.inspections[name]}
        return {"error": f"Inspection '{name}' not found in node '{node}'"}

    # Search all nodes
    for nid, n in state.nodes.items():
        if name in n.inspections:
            return {"node": nid, "inspection": n.inspections[name]}

    return {"error": f"Inspection '{name}' not found"}


async def ask_user(
    question: str,
    options: Optional[list[str]] = None,
    server_url: str = "http://localhost:2048",
) -> dict[str, Any]:
    """Send a question/suggestion to the terminal UI.

    Args:
        question: The question to ask.
        options: Optional list of valid responses.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            event = {
                "type": "ask",
                "question": question,
                "options": options,
                "timestamp": time.time(),
            }
            resp = await client.post(f"{server_url}/ingest", json=[event], timeout=5.0)
            resp.raise_for_status()
            return {"status": "question_sent", "question": question}
        except Exception as e:
            return {"error": str(e)}

"""MCP tool implementations for graphbook beta.

Observation tools query pipeline state. Action tools control pipeline lifecycle.
All tools communicate with the daemon server via HTTP using only stdlib (no httpx needed).
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional


_DEFAULT_URL = "http://localhost:2048"


def _get(url: str, timeout: float = 5.0) -> Any:
    """HTTP GET returning parsed JSON. Raises on failure."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, body: Any, timeout: float = 10.0) -> Any:
    """HTTP POST with JSON body, returning parsed JSON. Raises on failure."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e


# ─── Observation Tools ───────────────────────────────────────────────────────

async def get_graph(run_id: Optional[str] = None, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get the full DAG structure with nodes, edges, and execution status."""
    try:
        if run_id:
            return _get(f"{server_url}/runs/{run_id}/graph")
        else:
            return _get(f"{server_url}/graph")
    except Exception:
        from graphbook.beta.core.state import get_state
        return get_state().get_graph_dict()


async def get_node_status(name: str, run_id: Optional[str] = None, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get detailed status for a specific node."""
    try:
        if run_id:
            return _get(f"{server_url}/runs/{run_id}/nodes/{name}")
        else:
            return _get(f"{server_url}/nodes/{name}")
    except Exception:
        from graphbook.beta.core.state import get_state
        state = get_state()
        node = state.nodes.get(name)
        if node is None:
            return {"error": f"Node '{name}' not found"}
        return {
            "name": node.name, "func_name": node.func_name,
            "docstring": node.docstring, "exec_count": node.exec_count,
            "is_source": node.is_source, "params": node.params,
            "recent_logs": node.logs[-20:], "errors": node.errors,
            "progress": node.progress,
        }


async def get_logs(
    node: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
    server_url: str = _DEFAULT_URL,
) -> dict[str, Any]:
    """Get recent logs, optionally filtered by node and run."""
    try:
        params_parts = [f"limit={limit}"]
        if node:
            params_parts.append(f"node={urllib.request.quote(node)}")
        qs = "&".join(params_parts)
        if run_id:
            url = f"{server_url}/runs/{run_id}/logs?{qs}"
        else:
            url = f"{server_url}/logs?{qs}"
        return _get(url)
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
    server_url: str = _DEFAULT_URL,
) -> dict[str, Any]:
    """Get metric time series data for a node."""
    # Try daemon first (node status includes metrics)
    try:
        result = _get(f"{server_url}/nodes/{node}")
        if "error" not in result:
            metrics = result.get("metrics", {})
            if name:
                if name in metrics:
                    return {"node": node, "metrics": {name: metrics[name]}}
                return {"error": f"Metric '{name}' not found for node '{node}'"}
            return {"node": node, "metrics": metrics}
    except Exception:
        pass
    # Fallback to local state
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
        "metrics": {k: [{"step": s, "value": v} for s, v in entries] for k, entries in metrics.items()},
    }


async def get_errors(run_id: Optional[str] = None, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get all exceptions/errors, with full tracebacks and node context."""
    try:
        if run_id:
            url = f"{server_url}/runs/{run_id}/errors"
        else:
            url = f"{server_url}/errors"
        return _get(url)
    except Exception:
        from graphbook.beta.core.state import get_state
        state = get_state()
        all_errors = []
        for n in state.nodes.values():
            all_errors.extend(n.errors)
        return {"errors": all_errors}


async def get_description(server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get workflow description and all node docstrings."""
    # Try daemon first (graph includes workflow_description and node docstrings)
    try:
        graph = _get(f"{server_url}/graph")
        return {
            "workflow_description": graph.get("workflow_description"),
            "node_descriptions": {
                nid: n.get("docstring") for nid, n in graph.get("nodes", {}).items()
                if n.get("docstring")
            },
        }
    except Exception:
        pass
    from graphbook.beta.core.state import get_state
    state = get_state()
    return {
        "workflow_description": state.workflow_description,
        "node_descriptions": {nid: n.docstring for nid, n in state.nodes.items() if n.docstring},
    }



# ─── Action Tools ────────────────────────────────────────────────────────────

async def run_pipeline(
    script_path: str,
    args: Optional[list[str]] = None,
    name: Optional[str] = None,
    server_url: str = _DEFAULT_URL,
) -> dict[str, Any]:
    """Start a pipeline script via the daemon.

    Args:
        script_path: Path to the Python script.
        args: Command-line arguments for the script.
        name: Optional run name/ID.
    """
    run_id = name or f"run_{int(time.time())}"

    try:
        result = _post(
            f"{server_url}/run",
            {"script_path": script_path, "args": args or [], "run_id": run_id},
        )
        result["source"] = "daemon"
        return result
    except Exception as e:
        # Fallback: start subprocess directly
        import subprocess
        import sys
        import os

        env = os.environ.copy()
        env["GRAPHBOOK_SERVER_PORT"] = str(server_url.split(":")[-1])
        env["GRAPHBOOK_RUN_ID"] = run_id
        env["GRAPHBOOK_MODE"] = "server"

        proc = subprocess.Popen(
            [sys.executable, script_path] + (args or []),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return {"run_id": run_id, "pid": proc.pid, "status": "started", "source": "fallback", "error": str(e)}


async def stop_pipeline(run_id: str, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Stop a running pipeline by run ID."""
    try:
        return _post(f"{server_url}/runs/{run_id}/stop", {})
    except Exception as e:
        return {"error": f"Failed to stop pipeline: {e}"}


async def restart_pipeline(run_id: str, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Stop and re-run a pipeline with the same script and args."""
    try:
        # Get run info first
        run_info = _get(f"{server_url}/runs/{run_id}")

        # Stop if running
        await stop_pipeline(run_id, server_url)

        # Re-run with same params
        return await run_pipeline(
            script_path=run_info["script_path"],
            args=run_info.get("args", []),
            name=f"{run_id}_restart_{int(time.time())}",
            server_url=server_url,
        )
    except Exception as e:
        return {"error": f"Failed to restart pipeline: {e}"}


async def get_run_status(run_id: str, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get the status of a specific run."""
    try:
        return _get(f"{server_url}/runs/{run_id}")
    except Exception as e:
        return {"error": f"Run '{run_id}' not found: {e}"}


async def get_run_history(server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Get a list of all runs with outcomes, timestamps, and error counts."""
    try:
        return _get(f"{server_url}/runs")
    except Exception as e:
        return {"error": f"Could not get run history: {e}"}


async def get_source_code(file_path: str, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Read a pipeline source file.

    Args:
        file_path: Path to the source file.
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        content = path.read_text(encoding="utf-8")
        return {"file_path": str(path.resolve()), "content": content, "size": len(content)}
    except Exception as e:
        return {"error": f"Could not read file: {e}"}


async def write_source_code(
    file_path: str,
    content: Optional[str] = None,
    patches: Optional[list[dict[str, str]]] = None,
    server_url: str = _DEFAULT_URL,
) -> dict[str, Any]:
    """Write or patch a pipeline source file.

    Args:
        file_path: Path to the source file.
        content: Full file content (replaces entire file).
        patches: List of {old: str, new: str} patches to apply.
    """
    path = Path(file_path)

    if content is not None:
        try:
            path.write_text(content, encoding="utf-8")
            return {"status": "written", "file_path": str(path.resolve()), "size": len(content)}
        except Exception as e:
            return {"error": f"Could not write file: {e}"}

    if patches:
        try:
            current = path.read_text(encoding="utf-8")
            for patch in patches:
                old = patch.get("old", "")
                new = patch.get("new", "")
                if old not in current:
                    return {"error": f"Patch target not found in file: {old[:80]}..."}
                current = current.replace(old, new, 1)
            path.write_text(current, encoding="utf-8")
            return {"status": "patched", "file_path": str(path.resolve()), "patches_applied": len(patches)}
        except Exception as e:
            return {"error": f"Could not patch file: {e}"}

    return {"error": "Either 'content' or 'patches' must be provided"}


async def wait_for_event(
    timeout: float = 300,
    events: Optional[list[str]] = None,
    run_id: Optional[str] = None,
    server_url: str = _DEFAULT_URL,
) -> dict[str, Any]:
    """Block until a pipeline event occurs or timeout elapses.

    Args:
        timeout: Max seconds to wait (default 300).
        events: Event types to wait for (default: error, completed, ask_prompt).
        run_id: Run ID. Uses latest run if omitted.
    """
    if events is None:
        events = ["error", "completed", "ask_prompt"]

    # Resolve run_id to latest if not provided
    if not run_id:
        try:
            runs = _get(f"{server_url}/runs")
            active = runs.get("active_run")
            if active:
                run_id = active
            else:
                run_list = runs.get("runs", [])
                if run_list:
                    run_id = run_list[-1]["id"]
                else:
                    return {"error": "No runs found"}
        except Exception as e:
            return {"error": f"Could not resolve run_id: {e}"}

    types_str = ",".join(events)
    since = time.time()
    url = f"{server_url}/runs/{run_id}/events/wait?types={types_str}&timeout={timeout}&since={since}"

    try:
        return _get(url, timeout=timeout + 5)
    except Exception as e:
        return {"error": f"wait_for_event failed: {e}"}


async def ask_user(question: str, options: Optional[list[str]] = None, server_url: str = _DEFAULT_URL) -> dict[str, Any]:
    """Send a question to the terminal UI for human input."""
    try:
        import uuid
        event = {
            "type": "ask_prompt",
            "ask_id": str(uuid.uuid4()),
            "question": question,
            "options": options,
            "timestamp": time.time(),
        }
        return _post(f"{server_url}/events", [event])
    except Exception as e:
        return {"error": str(e)}

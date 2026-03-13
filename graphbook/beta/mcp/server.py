"""MCP server for graphbook beta.

Exposes both observation tools (query state) and action tools (control pipelines)
via the Model Context Protocol.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from graphbook.beta.mcp import tools


MCP_TOOLS = [
    # ── Observation Tools ──
    {
        "name": "graphbook_get_graph",
        "description": "Get the full DAG structure of the running pipeline. Returns nodes (with docstrings, source/non-source status, execution counts), edges, and workflow description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Optional run ID. Uses latest run if omitted."},
            },
        },
    },
    {
        "name": "graphbook_get_node_status",
        "description": "Get detailed status for a specific node. Includes execution count, params, docstring, recent logs, errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The node name."},
                "run_id": {"type": "string", "description": "Optional run ID."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "graphbook_get_logs",
        "description": "Get recent log entries, optionally filtered by node and run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Optional node name filter."},
                "run_id": {"type": "string", "description": "Optional run ID."},
                "limit": {"type": "integer", "description": "Max entries (default 100)."},
            },
        },
    },
    {
        "name": "graphbook_get_metrics",
        "description": "Get metric time series for a node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "The node name."},
                "name": {"type": "string", "description": "Optional specific metric name."},
            },
            "required": ["node"],
        },
    },
    {
        "name": "graphbook_get_errors",
        "description": "Get all errors with full tracebacks, node context, and param values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Optional run ID."},
            },
        },
    },
    {
        "name": "graphbook_get_description",
        "description": "Get workflow-level description and all node docstrings.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ── Action Tools ──
    {
        "name": "graphbook_run_pipeline",
        "description": "Start a pipeline script. Returns a run_id for tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_path": {"type": "string", "description": "Path to the Python script."},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Script arguments."},
                "name": {"type": "string", "description": "Optional run name/ID."},
            },
            "required": ["script_path"],
        },
    },
    {
        "name": "graphbook_stop_pipeline",
        "description": "Stop a running pipeline by run ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "The run ID to stop."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "graphbook_restart_pipeline",
        "description": "Stop and re-run a pipeline with the same script and args.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "The run ID to restart."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "graphbook_get_run_status",
        "description": "Get the status of a run: running, completed, crashed, stopped. Includes exit code, duration, error summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "The run ID."},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "graphbook_get_run_history",
        "description": "List all runs with outcomes, timestamps, and error counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "graphbook_get_source_code",
        "description": "Read the pipeline source file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the source file."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "graphbook_write_source_code",
        "description": "Write or patch a pipeline source file. Provide either full content or patches.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the source file."},
                "content": {"type": "string", "description": "Full file content (replaces file)."},
                "patches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                    },
                    "description": "List of {old, new} patches to apply.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "graphbook_wait_for_event",
        "description": "Block until a pipeline event occurs or timeout. Returns event details on match, or timeout status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timeout": {"type": "number", "description": "Max seconds to wait (default 300)."},
                "events": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Event types to wait for: error, completed, ask_prompt (default all three).",
                },
                "run_id": {"type": "string", "description": "Run ID. Uses latest run if omitted."},
            },
        },
    },
    {
        "name": "graphbook_ask_user",
        "description": "Send a question to the user via the terminal dashboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask."},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Valid response options."},
            },
            "required": ["question"],
        },
    },
]


async def handle_tool_call(name: str, arguments: dict[str, Any], server_url: str = "http://localhost:2048") -> Any:
    """Dispatch an MCP tool call to the appropriate handler."""
    handlers = {
        # Observation
        "graphbook_get_graph": lambda a: tools.get_graph(a.get("run_id"), server_url),
        "graphbook_get_node_status": lambda a: tools.get_node_status(a["name"], a.get("run_id"), server_url),
        "graphbook_get_logs": lambda a: tools.get_logs(a.get("node"), a.get("run_id"), a.get("limit", 100), server_url),
        "graphbook_get_metrics": lambda a: tools.get_metrics(a["node"], a.get("name"), server_url),
        "graphbook_get_errors": lambda a: tools.get_errors(a.get("run_id"), server_url),
        "graphbook_get_description": lambda a: tools.get_description(server_url),
        # Action
        "graphbook_run_pipeline": lambda a: tools.run_pipeline(a["script_path"], a.get("args"), a.get("name"), server_url),
        "graphbook_stop_pipeline": lambda a: tools.stop_pipeline(a["run_id"], server_url),
        "graphbook_restart_pipeline": lambda a: tools.restart_pipeline(a["run_id"], server_url),
        "graphbook_get_run_status": lambda a: tools.get_run_status(a["run_id"], server_url),
        "graphbook_get_run_history": lambda a: tools.get_run_history(server_url),
        "graphbook_get_source_code": lambda a: tools.get_source_code(a["file_path"], server_url),
        "graphbook_write_source_code": lambda a: tools.write_source_code(a["file_path"], a.get("content"), a.get("patches"), server_url),
        "graphbook_wait_for_event": lambda a: tools.wait_for_event(a.get("timeout", 300), a.get("events"), a.get("run_id"), server_url),
        "graphbook_ask_user": lambda a: tools.ask_user(a["question"], a.get("options"), server_url),
    }
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    return await handler(arguments)


def run_mcp_server(port: int = 2048) -> None:
    """Run the MCP server in stdio mode (JSON-RPC over stdin/stdout)."""
    from graphbook.beta.mcp.stdio import run_stdio_bridge
    run_stdio_bridge(port=port)

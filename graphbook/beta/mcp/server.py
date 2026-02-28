"""MCP server for graphbook beta.

Exposes graphbook state as MCP tools that AI agents can call.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from graphbook.beta.mcp import tools


# MCP Tool definitions for registration
MCP_TOOLS = [
    {
        "name": "graphbook_get_graph",
        "description": "Get the full DAG structure of the running graphbook pipeline. Returns nodes (with docstrings, source/non-source status, execution counts), edges, and workflow description.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "graphbook_get_node_status",
        "description": "Get detailed status for a specific node in the pipeline. Includes execution count, parameters, docstring, recent logs, errors, and source/non-source classification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The node name/identifier.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "graphbook_get_logs",
        "description": "Get recent log entries from the pipeline, optionally filtered by node name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Optional node name to filter logs by.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log entries (default 100).",
                    "default": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "graphbook_get_metrics",
        "description": "Get metric time series data for a node. Returns step/value pairs for tracked metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "The node name.",
                },
                "name": {
                    "type": "string",
                    "description": "Optional specific metric name.",
                },
            },
            "required": ["node"],
        },
    },
    {
        "name": "graphbook_get_errors",
        "description": "Get all exceptions and errors across the pipeline. Returns tracebacks enriched with node context (docstring, execution count, parameters).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "graphbook_get_description",
        "description": "Get the workflow description from gb.md() calls and all node docstrings. Useful for understanding what the pipeline does.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "graphbook_inspect_object",
        "description": "Get the last inspection result for a named object. Returns metadata like shape, dtype, device — no raw data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The inspection name.",
                },
                "node": {
                    "type": "string",
                    "description": "Optional node to search in.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "graphbook_ask_user",
        "description": "Send a question or suggestion to the user via the terminal UI. The user can respond, and their answer will be returned.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of valid response options.",
                },
            },
            "required": ["question"],
        },
    },
]


async def handle_tool_call(name: str, arguments: dict[str, Any], server_url: str = "http://localhost:2048") -> Any:
    """Dispatch an MCP tool call to the appropriate handler.

    Args:
        name: The tool name.
        arguments: Tool arguments.
        server_url: The graphbook server URL.

    Returns:
        The tool result.
    """
    handlers = {
        "graphbook_get_graph": lambda args: tools.get_graph(server_url),
        "graphbook_get_node_status": lambda args: tools.get_node_status(args["name"], server_url),
        "graphbook_get_logs": lambda args: tools.get_logs(args.get("node"), args.get("limit", 100), server_url),
        "graphbook_get_metrics": lambda args: tools.get_metrics(args["node"], args.get("name"), server_url),
        "graphbook_get_errors": lambda args: tools.get_errors(server_url),
        "graphbook_get_description": lambda args: tools.get_description(server_url),
        "graphbook_inspect_object": lambda args: tools.inspect_object(args["name"], args.get("node"), server_url),
        "graphbook_ask_user": lambda args: tools.ask_user(args["question"], args.get("options"), server_url),
    }

    handler = handlers.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}

    return await handler(arguments)


def run_mcp_server(port: int = 2048, mcp_port: int = 2049) -> None:
    """Run the MCP server as a standalone process.

    This is a stdio-based MCP server that reads JSON-RPC messages from stdin
    and writes responses to stdout.

    Args:
        port: The graphbook HTTP server port.
        mcp_port: The MCP server port (unused for stdio mode).
    """
    import sys

    server_url = f"http://localhost:{port}"

    async def _run():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        w_transport, w_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, asyncio.get_event_loop())

        while True:
            line = await reader.readline()
            if not line:
                break

            try:
                request = json.loads(line.decode())
                method = request.get("method", "")
                req_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {
                                "name": "graphbook-beta",
                                "version": "0.14.0-beta",
                            },
                        },
                    }
                elif method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"tools": MCP_TOOLS},
                    }
                elif method == "tools/call":
                    params = request.get("params", {})
                    tool_name = params.get("name", "")
                    tool_args = params.get("arguments", {})
                    result = await handle_tool_call(tool_name, tool_args, server_url)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, default=str),
                                }
                            ],
                        },
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {},
                    }

                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()

            except Exception as e:
                if req_id:
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": str(e)},
                    }
                    writer.write((json.dumps(error_response) + "\n").encode())
                    await writer.drain()

    asyncio.run(_run())

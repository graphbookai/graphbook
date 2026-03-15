# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

- **Install dependencies**: `poetry install --with dev`
- **Build core web UI**: `make web`
- **Build beta web UI**: `make web-beta`
- **Build docs**: `make docs`
- **Package for PyPI**: `make package` (builds both web UIs, copies assets, runs `poetry build`)
- **Run core server** (dev): `python graphbook/core/cli.py --web_dir web/dist` (port 8005)
- **Run beta daemon**: `graphbook-beta serve` (port 2048)
- **Run beta pipeline**: `graphbook-beta run <script.py>`
- **Run all tests**: `pytest`
- **Run single test**: `pytest tests/beta/test_decorators.py::TestFnDecorator::test_fn_registers_node -v`
- **Dev frontend** (core): `cd web && npm install && npm run dev` → localhost:5173, set Graph Server Host to localhost:8005
- **Dev frontend** (beta): `cd web_beta && npm install && npm run dev` → localhost:5173, proxies to daemon on localhost:2048

## Architecture

Graphbook contains **two distinct frameworks** in one package:

### Core (`graphbook/core/`) — Visual DAG Editor
Class-based OOP framework for building interactive ML data pipelines with a visual editor.

- **Step system** (`core/steps/base.py`): Base classes `Step`, `BatchStep`, `SourceStep`, `AsyncStep`, `GeneratorSourceStep`. Lifecycle methods: `on_data()`, `on_batch()`, `on_item_batch()`, `on_end()`, `on_start()`. Decorators in `core/decorators.py` (`@step`, `@batch`, `@source`, `@param`, `@output`, `@resource`).
- **Execution** (`core/processing/`): `GraphProcessor` runs DAGs via multiprocessing worker pools with queue-based communication. `GraphState` tracks step instances, parent/child relationships, and caching. Topological sort via DFS.
- **Server** (`core/web.py`): aiohttp + WebSocket. Serves the React UI and manages client sessions.
- **Serialization** (`core/serialization.py`): Workflows serialize as JSON or Python files.
- **Plugins** (`core/plugins.py`): `export()` decorator registers custom Step/Resource classes. `NodeHub` watches `custom_nodes/` directory with hot-reload via watchdog.
- **Web UI** (`web/`): React 18 + Ant Design + ReactFlow + CodeMirror. Built output goes to `web/dist/`, copied to `graphbook/web/` during packaging.

### Beta (`graphbook/beta/`) — Lightweight Observability
Decorator-based framework for instrumenting Python functions with automatic DAG inference.

- **Decorators** (`beta/core/decorators.py`): `@gb.fn()` registers functions as nodes. DAG edges inferred automatically from data flow between decorated functions (configurable strategy: object tracking, stack-based, both, or none). Supports explicit `depends_on`.
- **State** (`beta/core/state.py`): `SessionState` singleton tracks nodes, edges, logs, metrics, errors. `NodeInfo` per node.
- **Logging** (`beta/logging/logger.py`): `gb.log()`, `gb.log_metric()`, `gb.log_image()`, `gb.log_text()`, `gb.md()`. Extensible via `LoggingBackend` protocol.
- **Modes**: Auto-detects daemon or falls back to local Rich terminal output. Controlled by `GRAPHBOOK_MODE` env var.
- **Daemon** (`beta/server/daemon.py`): FastAPI + uvicorn. Persistent server that survives pipeline crashes. Tracks runs with logs, metrics, errors. REST + WebSocket APIs for streaming events.
- **MCP** (`beta/mcp/`): Model Context Protocol tools for AI agent integration.
- **CLI** (`beta/cli.py`): `graphbook-beta serve|run|status|stop|logs|errors|mcp`
- **Web UI** (`web_beta/`): React 19 + Tailwind + Zustand + XYFlow. Built output goes to `web_beta/dist/`, copied to `graphbook/beta/server/static/` during packaging.

### Entry Points (pyproject.toml)
- `graphbook` → `graphbook.core.cli:main`
- `graphbook-beta` → `graphbook.beta.cli:main`

### Tests
- `tests/unit/` — Core framework unit tests (decorators, utils, doc2md)
- `tests/beta/` — Beta framework tests (decorators, logging, daemon, MCP, CLI, server, client)
- `tests/e2e/` — End-to-end workflow tests

## Code Style
- **Python >=3.10** (per pyproject.toml `requires-python`)
- Imports: group standard lib, third-party, and internal with blank line separators
- Type annotations on function parameters and return types
- PascalCase classes, snake_case functions/methods
- Detailed docstrings (converted to markdown with doc2md)
- Specific exception handling (no bare `except`)
- Early returns for error paths
- UPPERCASE constants
- `pathlib.Path` over string paths
- Class organization: properties/attributes first, then methods

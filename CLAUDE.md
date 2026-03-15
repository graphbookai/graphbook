# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands
- Build web UI: `cd web && npm install && npm run build`
- Build docs: `make docs`
- Package project: `make package`
- Run server: `python graphbook/core/cli.py --web_dir web/dist`
- Run tests: `pytest`
- Run single test: `pytest tests/e2e/test_example_workflows.py::test_run_example_workflow -v`
- Install dependencies: `uv sync --group dev`

## Code Style Guidelines
- Python version: 3.10+
- Imports: group standard lib, third-party, and internal imports with blank line separators
- Types: use type annotations for function parameters and return types
- Naming: Classes use PascalCase, functions/methods use snake_case
- Documentation: use detailed docstrings (converted to markdown with doc2md)
- Avoid bare except; use specific exception handling
- Error paths should return early
- Constants in UPPERCASE
- Use Path objects from pathlib over string paths
- Class organization: properties/attributes first, then methods

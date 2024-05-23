# Graphbook
Graphbook is an extensible and interactive ML workflow editor that allows you to build monitorable data processing pipelines powered with ML. It can be used to prepare training data for custom ML models, experiment with custom trained or off-the-shelf models, and to build ML-based ETL applications. Custom nodes can be built in Python, and Graphbook will behave like a framework and call lifecycle methods on those nodes.

## Current Features
- Graph-based visual editor to experiment and create complex ML workflows
- Internal Python code editor
- Executable graph, subgraphs, and individual nodes
- Only re-executes parts of the workflow that changes between executions
- Node logging and output views for monitoring in the UI
- Custom buildable nodes with Python
- Automatic batching for Pytorch tensors
- Multiprocessing I/O to and from disk and network
- Customizeable multiprocessing functions
- Basic nodes for filtering, loading, and saving outputs

## Getting Started
View the docs to learn how to install and get started with Graphbook.

## Collaboration Guide
This is a guide on how to get started developing Graphbook. If you are simply using Graphbook, view the [Getting Started](#getting-started) section.
1. Install python>=3.11.2. There is a known bug in python 3.10.
1. Clone and `cd graphbook/`
1. (Optional) Create your venv
1. `pip install -r requirements.txt`
1. `pip install -r docs/requirements.txt`
1. `python src/server.py`
1. `cd web`
1. `npm install`
1. `npm run dev`

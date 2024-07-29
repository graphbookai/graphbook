<p align="center">
  <a href="https://graphbook.ai">
    <img src="docs/_static/graphbook.png" alt="Logo" width=256>
  </a>

  <h1 align="center">Graphbook</h1>

  <p align="center">
    The ML workflow framework
    <br>
    <a href="https://github.com/graphbookai/graphbook/issues/new?template=bug.md">Report bug</a>
    ·
    <a href="https://github.com/graphbookai/graphbook/issues/new?template=feature.md&labels=feature">Request feature</a>
  </p>

  <p align="center">
    <a href="#overview">Overview</a> •
    <a href="#current-features">Current Features</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#examples">Examples</a> •
    <a href="#collaboration">Collaboration</a>
  </p>
</p>

## Overview
Graphbook is a framework for building efficient, visual DAG-structured ML workflows composed of nodes written in Python. Graphbook provides common ML processing features such as multiprocessing IO and automatic batching, and it features a web-based UI to assemble, monitor, and execute data processing workflows. It can be used to prepare training data for custom ML models, experiment with custom trained or off-the-shelf models, and to build ML-based ETL applications. Custom nodes can be built in Python, and Graphbook will behave like a framework and call lifecycle methods on those nodes.

## Current Features
- ​​Graph-based visual editor to experiment and create complex ML workflows
- Caches outputs and only re-executes parts of the workflow that changes between executions
- UI monitoring components for logs and outputs per node
- Custom buildable nodes with Python
- Automatic batching for Pytorch tensors
- Multiprocessing I/O to and from disk and network
- Customizable multiprocessing functions
- Ability to execute entire graphs, or individual subgraphs/nodes
- Ability to execute singular batches of data
- Ability to pause graph execution
- Basic nodes for filtering, loading, and saving outputs
- Node grouping and subflows
- Autosaving and shareable serialized workflow files
- Registers node code changes without needing a restart
- Monitorable CPU and GPU resource usage

## Getting Started
### Install from PyPI
1. `pip install graphbook`
1. `graphbook`
1. Visit http://localhost:8007

### Install with Docker
1. Pull and run the downloaded image
    ```bash
    docker run --rm -p 8005:8005 -p 8006:8006 -p 8007:8007 -v $PWD/workflows:/app/workflows rsamf/graphbook:latest
    ```
1. Visit http://localhost:8007

Visit the [docs](https://docs.graphbook.ai) to learn more on how to create custom nodes and workflows with Graphbook.

## Examples
We continually post examples of workflows and custom nodes in our [examples repo](https://github.com/graphbookai/graphbook-examples).

## Collaboration
This is a guide on how to get started developing Graphbook. If you are simply using Graphbook, view the [Getting Started](#getting-started) section.

### Run Graphbook in Development Mode
You can use any other virtual environment solution, but `poetry` is used in the steps below.
1. Clone the repo and `cd graphbook`
1. `poetry install --with dev`
1. `poetry shell`
1. `python graphbook/server.py`
1. `cd web`
1. `npm install`
1. `npm run dev`

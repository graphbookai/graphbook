<p align="center">
  <a href="https://graphbook.ai">
    <img src="docs/_static/graphbook.png" alt="Logo" width=256>
  </a>

  <h1 align="center">Graphbook</h1>

  <p align="center">
    The ML workflow framework
    <br>
    <a href="https://github.com/graphbookai/graphbook/issues/new?template=bug_report.md&labels=bug">Report bug</a>
    ·
    <a href="https://github.com/graphbookai/graphbook/issues/new?template=feature_request.md&labels=enhancement">Request feature</a>
  </p>

  <p align="center">
    <a href="#overview">Overview</a> •
    <a href="#status">Status</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#examples">Examples</a> •
    <a href="#collaboration">Collaboration</a>
  </p>
</p>

## Overview
Graphbook is a framework for building efficient, visual DAG-structured ML workflows composed of nodes written in Python. Graphbook provides common ML processing features such as multiprocessing IO and automatic batching, and it features a web-based UI to assemble, monitor, and execute data processing workflows. It can be used to prepare training data for custom ML models, experiment with custom trained or off-the-shelf models, and to build ML-based ETL applications. Custom nodes can be built in Python, and Graphbook will behave like a framework and call lifecycle methods on those nodes.

## Status
Graphbook is in a very early stage of development, so expect minor bugs and rapid design changes through the coming releases. If you would like to [report a bug](https://github.com/graphbookai/graphbook/issues/new?template=bug_report.md&labels=bug) or [request a feature](https://github.com/graphbookai/graphbook/issues/new?template=feature_request.md&labels=enhancement), please feel free to do so. We aim to make Graphbook serve our users in the best way possible.

### Current Features
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

### Planned Features
- Graphbook services and remote DAGs for scalable workflows
- A `graphbook run` command to execute workflows in a CLI
- Step/Resource functions to reduce verbosity
- Human-in-the-loop Steps for manual feedback/control during DAG execution
- All-code workflows, so users never have to leave their IDE
- UI extensibility
- And many optimizations for large data processing workloads

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
Graphbook is in active development and very much welcomes contributors. This is a guide on how to run Graphbook in development mode. If you are simply using Graphbook, view the [Getting Started](#getting-started) section. 

### Run Graphbook in Development Mode
You can use any other virtual environment solution, but it is highly adviced to use [poetry](https://python-poetry.org/docs/) since our dependencies are specified in poetry's format.
1. Clone the repo and `cd graphbook`
1. `poetry install --with dev`
1. `poetry shell`
1. `python graphbook/server.py`
1. `cd web`
1. `npm install`
1. `npm run dev`

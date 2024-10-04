<p align="center">
  <a href="https://graphbook.ai">
    <img src="docs/_static/graphbook.png" alt="Logo" width=256>
  </a>

  <h1 align="center">Graphbook</h1>

  <p align="center">
    <a href="https://github.com/graphbookai/graphbook/blob/main/LICENSE">
      <img alt="GitHub License" src="https://img.shields.io/github/license/graphbookai/graphbook">
    </a>
    <a href="https://github.com/graphbookai/graphbook/actions/workflows/pypi.yml">
      <img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/graphbookai/graphbook/pypi.yml">
    </a>
    <a href="https://hub.docker.com/r/rsamf/graphbook">
      <img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/rsamf/graphbook">
    </a>
    <a href="https://www.pepy.tech/projects/graphbook">
      <img alt="PyPI Downloads" src="https://static.pepy.tech/badge/graphbook">
    </a>
    <a href="https://pypi.org/project/graphbook/">
      <img alt="PyPI - Version" src="https://img.shields.io/pypi/v/graphbook">
    </a>
  </p>
  <div align="center">
    <a href="https://discord.gg/XukMUDmjnt">
      <img alt="Join Discord" src="https://img.shields.io/badge/Join%20our%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white">
    </a>
  </div>
  <p align="center">
    <a href="https://discord.gg/XukMUDmjnt">
      <img alt="Discord" src="https://img.shields.io/discord/1199855707567177860">
    </a>
  </p>

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
Graphbook is a framework for building efficient, visual DAG-structured ML workflows composed of nodes written in Python. Graphbook provides common ML processing features such as multiprocessing IO and automatic batching for PyTorch tensors, and it features a web-based UI to assemble, monitor, and execute data processing workflows. It can be used to prepare training data for custom ML models, experiment with custom trained or off-the-shelf models, and to build ML-based ETL applications. Custom nodes can be built in Python, and Graphbook will behave like a framework and call lifecycle methods on those nodes.

<p align="center">
  <a href="https://graphbook.ai">
    <img src="https://media.githubusercontent.com/media/rsamf/public/main/docs/overview/huggingface-pipeline-demo.gif" alt="Huggingface Pipeline Demo" width="512">
  </a>
  <div align="center">Build, run, monitor!</div>
</p>

## Status
Graphbook is in a very early stage of development, so expect minor bugs and rapid design changes through the coming releases. If you would like to [report a bug](https://github.com/graphbookai/graphbook/issues/new?template=bug_report.md&labels=bug) or [request a feature](https://github.com/graphbookai/graphbook/issues/new?template=feature_request.md&labels=enhancement), please feel free to do so. We aim to make Graphbook serve our users in the best way possible.

### Current Features
- ​​Graph-based visual editor to experiment and create complex ML workflows
- Caches outputs and only re-executes parts of the workflow that changes between executions
- UI monitoring components for logs and outputs per node
- Custom buildable nodes with Python via OOP and functional patterns
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
- Human-in-the-loop prompting for interactivity and manual control during DAG execution
- (BETA) Third Party Plugins *

\* We plan on adding documentation for the community to build plugins, but for now, an example can be seen at
[example_plugin](example_plugin) and
[graphbook-huggingface](https://github.com/graphbookai/graphbook-huggingface)

### Planned Features
- A `graphbook run` command to execute workflows in a CLI
- All-code workflows, so users never have to leave their IDE
- Remote subgraphs for scaling workflows on other Graphbook services
- And many optimizations for large data processing workloads

### Supported OS
The following operating systems are supported in order of most to least recommended:
- Linux
- Mac
- Windows (not recommended) *

\* There may be issues with running Graphbook on Windows. With limited resources, we can only focus testing and development on Linux.

## Getting Started
### Install from PyPI
1. `pip install graphbook`
1. `graphbook`
1. Visit http://localhost:8005

### Install with Docker
1. Pull and run the downloaded image
    ```bash
    docker run --rm -p 8005:8005 -v $PWD/workflows:/app/workflows rsamf/graphbook:latest
    ```
1. Visit http://localhost:8005

### Recommended Plugins
* [Huggingface](https://github.com/graphbookai/graphbook-huggingface)

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
1. `python graphbook/main.py`
1. `cd web`
1. `npm install`
1. `npm run dev`

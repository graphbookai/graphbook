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
    The Framework for AI-driven Data Pipelines
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
Graphbook is a framework for building efficient, interactive DAG-structured AI data pipelines or workflows composed of nodes written in Python. Graphbook provides common ML processing features such as multiprocessing IO and automatic batching for PyTorch tensors, and it features a web-based UI to assemble, monitor, and execute data processing workflows. It can be used to prepare training data for custom ML models, experiment with custom trained or off-the-shelf models, and to build ML-based ETL applications. Custom nodes can be built in Python, and Graphbook will behave like a framework and call lifecycle methods on those nodes.

Try out the [demo](https://huggingface.co/spaces/rsamf/rmbg-graphbook)!

<p align="center">
  <a href="https://graphbook.ai">
    <img src="https://media.githubusercontent.com/media/rsamf/public/main/docs/overview/huggingface-pipeline-demo.gif" alt="Huggingface Pipeline Demo" width="512">
  </a>
  <div align="center">Build, run, monitor!</div>
</p>

### Applications
* Clean and curate custom large scale datasets
* [Demo ML apps](https://huggingface.co/spaces/rsamf/rmbg-graphbook) on Huggingface Spaces
* Build and deliver customizable no-code or hybrid low-code ML apps and services
* Quickly experiment with different ML models and adjust hyperparameters
* Maximize GPU utilization, parallelize IO, and scale across clusters
* Wrap your Ray DAGs with a frontend for end users

## Status
Graphbook is in a very early stage of development, so expect minor bugs and rapid design changes through the coming releases. If you would like to [report a bug](https://github.com/graphbookai/graphbook/issues/new?template=bug_report.md&labels=bug) or [request a feature](https://github.com/graphbookai/graphbook/issues/new?template=feature_request.md&labels=enhancement), please feel free to do so. We aim to make Graphbook serve our users in the best way possible.

### Current Features
* ​​Graph-based visual editor to experiment and create complex ML workflows
* Workflows can be serialized as Python and JSON files
* Caches outputs and only re-executes parts of the workflow that changes between executions
* UI monitoring components for logs and outputs per node
* Custom buildable nodes with Python via OOP and functional patterns
* Multiprocessing I/O to and from disk and network
* Customizable multiprocessing functions
* Ability to execute entire graphs, or individual subgraphs/nodes
* Ability to execute singular batches of data
* Ability to pause graph execution
* Basic nodes for filtering, loading, and saving outputs
* Node grouping and subflows
* Autosaving and shareable serialized workflow files
* Registers node code changes without needing a restart
* Monitorable system CPU and GPU resource usage
* Monitorable worker queue sizes for optimal worker scaling
* Human-in-the-loop prompting for interactivity and manual control during DAG execution
* Can switch to threaded processing per client session for demoing apps to multiple simultaneous users
* Scale with Ray: Build all-code workflows and scale pipelines on Ray clusters
* (BETA) Third Party Plugins *

\* We plan on adding documentation for the community to build plugins, but for now, an example can be seen at
[example_plugin](example_plugin) and
[graphbook-huggingface](https://github.com/graphbookai/graphbook-huggingface)

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
* [Graphbook Hugging Face](https://github.com/graphbookai/graphbook-huggingface)

Visit the [docs](https://docs.graphbook.ai) to learn more on how to create custom nodes and workflows with Graphbook.

## Examples
See plugin and workflow examples here in [this folder](/examples).

## Collaboration
Graphbook is in active development and very much welcomes contributors. If you would like to be actively involved in making Graphbook great, join our [discord](https://discord.gg/XukMUDmjnt).

### Run Graphbook in Development Mode
This is a guide on how to run Graphbook in development mode. If you are simply using Graphbook, view the [Getting Started](#getting-started) section.
You can use any other virtual environment solution, but it is highly adviced to use [poetry](https://python-poetry.org/docs/) since our dependencies are specified in poetry's format.
1. Clone the repo and `cd graphbook`
1. `poetry install --with dev`
1. `poetry shell`
1. `python graphbook/core/cli.py`
1. `cd web`
1. `deno install`
1. `deno run dev`
1. In your browser, navigate to localhost:5173, and in the settings, change your **Graph Server Host** to `localhost:8005`.

# Graphbook Beta

Lightweight observability for Python programs. Decorate your functions with `@gb.fn()`, and graphbook automatically infers a DAG from your call graph, captures logs, metrics, inspections, and errors — all queryable in real time via CLI, MCP tools, or a Rich terminal dashboard.

## Installation

```bash
pip install graphbook
```

The CLI entry point is `graphbook-beta`:

```bash
graphbook-beta --help
```

## Quick Start

```python
import graphbook.beta as gb

@gb.fn()
def load_data(path: str = "data.csv") -> list[dict]:
    """Load records from a file."""
    records = [{"id": i, "value": i * 0.5} for i in range(100)]
    gb.log(f"Loaded {len(records)} records from {path}")
    return records

@gb.fn()
def transform(records: list[dict]) -> list[dict]:
    """Normalize values."""
    out = []
    for r in gb.track(records, name="transforming"):
        out.append({**r, "value": r["value"] / 50.0})
    gb.log(f"Transformed {len(out)} records")
    gb.log_metric("record_count", float(len(out)))
    return out

@gb.fn()
def run():
    """Main pipeline entry point."""
    records = load_data()
    result = transform(records)
    gb.log(f"Pipeline complete: {len(result)} records")
    return result

if __name__ == "__main__":
    run()
```

Running this produces a Rich terminal display showing the DAG, node execution counts, logs, and progress bars. The DAG edges (`run → load_data`, `load_data → transform`) are inferred automatically from data flow — no manual wiring required.

## Core Concepts

### `@gb.fn()` — Register a function as a DAG node

Every function decorated with `@gb.fn()` becomes a node in the pipeline DAG. Edges are inferred from **data flow**: when a node's return value is passed as an argument to another node, an edge is created from the producer to the consumer.

```python
@gb.fn()
def load_data():
    return [1, 2, 3]

@gb.fn()
def transform(data):
    return [x * 2 for x in data]

@gb.fn()
def run():
    records = load_data()        # edge: run → load_data (no data dependency)
    result = transform(records)  # edge: load_data → transform (data flows from load_data)
    return result
```

When a child node receives no node-produced arguments, the edge falls back to the calling parent node.

You can use it in several ways:

```python
@gb.fn              # bare decorator
@gb.fn()            # with parentheses
@gb.fn(depends_on=[other_fn])  # with explicit dependencies
```

### `depends_on` — Explicit dependency declaration

Some dependencies cannot be detected automatically (shared mutable state, class attributes, global variables). Use `depends_on` to declare these explicitly:

```python
@gb.fn()
def setup():
    """Initialize shared resources."""
    ...

@gb.fn(depends_on=[setup])
def process():
    """Uses resources initialized by setup."""
    ...
```

`depends_on` accepts a list of decorated functions or node ID strings. Explicit dependencies are added alongside any auto-detected data-flow edges.

> **Limitation**: Graphbook tracks data flow via argument passing (`id()`-based return value tracking). Dependencies through shared mutable state, class attributes, closures, or global variables are **not** automatically detected. Use `depends_on` for these cases.

### `gb.log(message)` — Text logging

Log a message to the current node. Messages appear in the terminal dashboard and are queryable via MCP tools.

```python
@gb.fn()
def train(data):
    gb.log(f"Training on {len(data)} samples")
    for epoch in range(10):
        loss = do_train(data)
        gb.log(f"Epoch {epoch}: loss={loss:.4f}")
```

### `gb.log_metric(name, value, step=None)` — Scalar metrics

Log scalar metrics with automatic step counting. Useful for loss curves, accuracy, or any time series.

```python
@gb.fn()
def train(model, data):
    for epoch in range(100):
        loss = train_one_epoch(model, data)
        gb.log_metric("loss", loss)
        gb.log_metric("lr", optimizer.param_groups[0]["lr"])
```

### `gb.log_cfg(cfg)` — Configuration logging

Log configuration for the current node. Values are displayed in the Info tab.

```python
@gb.fn()
def train(lr=0.001, epochs=50):
    gb.log_cfg({"lr": lr, "epochs": epochs})
    ...
```

Multiple `log_cfg()` calls within the same node merge their dictionaries.

### `gb.track(iterable, name=None, total=None)` — Progress tracking

Wrap any iterable for tqdm-like progress tracking. The progress bar renders in the terminal dashboard and updates in real time.

```python
@gb.fn()
def process(items):
    for item in gb.track(items, name="processing"):
        transform(item)
```

### `gb.log_image(image, name=None, step=None)` — Image logging

Log images (PIL, NumPy arrays, or PyTorch tensors) for visual inspection.

```python
@gb.fn()
def augment(image):
    augmented = apply_transforms(image)
    gb.log_image(augmented, name="augmented")
    return augmented
```

### `gb.log_audio(audio, sr=16000, name=None, step=None)` — Audio logging

Log audio data for playback and analysis.

```python
@gb.fn()
def synthesize(text):
    waveform = tts_model(text)
    gb.log_audio(waveform, sr=22050, name="output")
    return waveform
```

### `gb.log_text(name, text)` — Rich text / Markdown logging

Log formatted text or Markdown content.

```python
@gb.fn()
def report(stats):
    gb.log_text("summary", f"""## Results
- **Accuracy**: {stats['acc']:.2%}
- **F1 Score**: {stats['f1']:.4f}
""")
```

### `gb.md(description)` — Workflow description

Set a workflow-level description (Markdown supported). This describes the overall pipeline and is visible in MCP tools and the dashboard.

```python
gb.md("""
# Image Classification Pipeline

This pipeline loads images, runs inference with a ResNet model,
and exports predictions to a JSON file.
""")
```

### `gb.ask(question, options=None, timeout=None)` — Human-in-the-loop

Pause the pipeline and ask the user a question via MCP or the terminal.

```python
@gb.fn()
def review(predictions):
    answer = gb.ask(
        "Model accuracy is 73%. Continue training?",
        options=["yes", "no", "retrain with more data"]
    )
    if answer == "no":
        return predictions
    ...
```

## CLI Reference

The `graphbook-beta` CLI provides commands for managing the daemon server and pipelines.

### Start the daemon server

```bash
# Foreground (interactive)
graphbook-beta serve

# Background (daemon mode)
graphbook-beta serve -d

# Custom port
graphbook-beta serve --port 3000
```

### Run a pipeline

```bash
graphbook-beta run my_pipeline.py
graphbook-beta run my_pipeline.py --name "experiment-1"
```

This auto-starts the daemon if it isn't running, sets environment variables (`GRAPHBOOK_MODE=server`, `GRAPHBOOK_SERVER_PORT`, `GRAPHBOOK_RUN_ID`), and streams events to the daemon in real time.

### Check status

```bash
graphbook-beta status
```

### View logs and errors

```bash
graphbook-beta logs
graphbook-beta logs --run experiment-1 --node train --limit 50
graphbook-beta errors
graphbook-beta errors --run experiment-1
```

### Stop the daemon

```bash
graphbook-beta stop
```

### MCP integration

```bash
# Print Claude Code / Claude Desktop MCP config
graphbook-beta mcp
```

## MCP Tools for AI Agents

Graphbook exposes 15 MCP tools for querying and controlling pipelines from an AI agent (e.g., Claude). The daemon server must be running.

### Observation Tools

| Tool | Description |
|------|-------------|
| `graphbook_get_graph` | Full DAG structure: nodes, edges, execution counts |
| `graphbook_get_node_status` | Detailed status for one node: logs, metrics, errors, params |
| `graphbook_get_logs` | Recent log entries, filterable by node and run |
| `graphbook_get_metrics` | Metric time series for a node |
| `graphbook_get_errors` | All errors with full tracebacks and node context |
| `graphbook_get_description` | Workflow description and all node docstrings |

### Action Tools

| Tool | Description |
|------|-------------|
| `graphbook_run_pipeline` | Start a pipeline script, returns a run ID |
| `graphbook_stop_pipeline` | Stop a running pipeline by run ID |
| `graphbook_restart_pipeline` | Stop and re-run a pipeline with same args |
| `graphbook_get_run_status` | Status of a specific run (running/completed/crashed) |
| `graphbook_get_run_history` | List all runs with outcomes and timestamps |
| `graphbook_get_source_code` | Read a pipeline source file |
| `graphbook_write_source_code` | Write or patch a pipeline source file |
| `graphbook_ask_user` | Send a question to the user via the terminal |
| `graphbook_wait_for_event` | Block until a pipeline event occurs or timeout elapses |

### Example: AI Agent Workflow

An AI agent can use these tools to autonomously run and debug pipelines:

1. Read the pipeline source with `get_source_code`
2. Start a run with `run_pipeline`
3. Monitor progress with `get_graph` and `get_node_status`
4. Check for errors with `get_errors`
5. View metrics with `get_metrics`
6. If something fails, read logs with `get_logs`, patch the code with `write_source_code`, and restart with `restart_pipeline`
7. Ask the user for guidance with `ask_user`

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Your Python  │────>│  Graphbook SDK   │────>│  Daemon Server │
│   Pipeline    │     │  (@fn, log,      │     │  (FastAPI,     │
│              │     │   track, ...)    │     │   port 2048)   │
└──────────────┘     └────────┬─────────┘     └───────┬────────┘
                              │                       │
                       ┌──────v──────┐ ┌──────────────┼──────────────┐
                       │  Terminal   │ │              │              │
                       │  Dashboard  │ │       ┌──────v─────┐ ┌─────v─────┐
                       │  (Rich)     │ │       │ MCP Tools │ │   Web UI  │
                       └─────────────┘ │       │ (Claude)  │ │           │
                                       │       └───────────┘ └───────────┘
                                 ┌─────v─────┐
                                 │   CLI     │
                                 │ graphbook-│
                                 │   beta    │
                                 └───────────┘
```

There are two execution modes:

- **Local mode** (default): In-process only. No daemon needed. Just run your script directly.
- **Server mode**: Events stream to a persistent daemon via HTTP. Use `graphbook-beta serve` to start the daemon, then `graphbook-beta run` to execute pipelines. MCP tools and the web UI query the daemon.

In both modes, a Rich terminal dashboard shows the DAG, progress, logs, and errors. In server mode, the dashboard also displays daemon connection status. Pass `terminal=False` to `gb.init()` to disable it.

When running via `graphbook-beta run`, the SDK auto-detects the daemon through environment variables and switches to server mode automatically.

## Complete Example: ML Training Pipeline

```python
import graphbook.beta as gb
import torch
import torch.nn as nn

gb.md("""
# MNIST Training Pipeline
Train a simple classifier on MNIST with configurable hyperparameters.
""")

@gb.fn()
def build_model(hidden_size: int = 128, dropout: float = 0.2) -> nn.Module:
    """Build a simple feedforward classifier."""
    gb.log_cfg({"hidden_size": hidden_size, "dropout": dropout})
    model = nn.Sequential(
        nn.Flatten(),
        nn.Linear(784, hidden_size),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(hidden_size, 10),
    )
    gb.log(f"Built model: hidden_size={hidden_size}, dropout={dropout}")
    return model

@gb.fn()
def train(lr: float = 0.001, epochs: int = 10, batch_size: int = 64):
    """Train the model on MNIST."""
    gb.log_cfg({"lr": lr, "epochs": epochs, "batch_size": batch_size})
    model = build_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    gb.log(f"Training: lr={lr}, epochs={epochs}, batch_size={batch_size}")

    for epoch in gb.track(range(epochs), name="epochs"):
        # ... training loop ...
        loss = 0.5 / (epoch + 1)  # placeholder
        acc = 0.8 + epoch * 0.02  # placeholder

        gb.log_metric("loss", loss)
        gb.log_metric("accuracy", acc)
        gb.log(f"Epoch {epoch}: loss={loss:.4f}, acc={acc:.2%}")

    gb.log("Training complete")
    return model

if __name__ == "__main__":
    train()
```

## API Reference

### Module: `graphbook.beta`

| Function | Signature | Description |
|----------|-----------|-------------|
| `fn` | `@fn()`, `@fn(depends_on=[...])` | Register a function as a DAG node |
| `log` | `log(message: str)` | Log a text message |
| `log_metric` | `log_metric(name, value, step=None)` | Log a scalar metric |
| `log_cfg` | `log_cfg(cfg: dict)` | Log node configuration to Info tab |
| `log_image` | `log_image(image, name=None, step=None)` | Log an image |
| `log_audio` | `log_audio(audio, sr=16000, name=None, step=None)` | Log audio data |
| `log_text` | `log_text(name, text)` | Log rich text / Markdown |
| `track` | `track(iterable, name=None, total=None)` | Progress tracking |
| `md` | `md(description: str)` | Set workflow description |
| `init` | `init(port, host, mode, backends, terminal, dag_strategy, flush_interval)` | Manual initialization |
| `ask` | `ask(question, options=None, timeout=None)` | Human-in-the-loop prompt |
| `get_state` | `get_state() -> SessionState` | Access the global state singleton |

### Logging Backends

Implement the `LoggingBackend` protocol to send events to external systems:

```python
from graphbook.beta import LoggingBackend

class MyBackend:
    def on_log(self, node: str, message: str, timestamp: float) -> None: ...
    def on_metric(self, node: str, name: str, value: float, step: int) -> None: ...
    def on_image(self, node: str, name: str, image_bytes: bytes, step: int) -> None: ...
    def on_audio(self, node: str, name: str, audio_bytes: bytes, sr: int) -> None: ...
    def on_node_start(self, node: str, params: dict) -> None: ...
    def on_node_end(self, node: str, duration: float) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...

gb.init(backends=[MyBackend()])
```

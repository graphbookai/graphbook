"""CLI entry points for graphbook beta.

Commands:
    graphbook serve   — Start the persistent daemon server
    graphbook run     — Run a pipeline as a managed subprocess
    graphbook status  — Show daemon status and recent runs
    graphbook stop    — Stop the daemon
    graphbook logs    — View logs from runs
    graphbook errors  — View errors from runs
    graphbook mcp     — Print MCP connection config for Claude Code
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_PID_DIR = Path.home() / ".graphbook"
_PID_FILE = _PID_DIR / "server.pid"


def _write_pid(pid: int) -> None:
    _PID_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid))


def _read_pid() -> int | None:
    try:
        if _PID_FILE.exists():
            return int(_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        pass
    return None


def _remove_pid() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _is_alive(port: int) -> bool:
    try:
        import httpx
        resp = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the persistent daemon server."""
    port = args.port
    host = args.host

    if _is_alive(port):
        print(f"Graphbook daemon is already running on {host}:{port}")
        return

    if args.daemon:
        # Background mode
        cmd = [
            sys.executable, "-m", "uvicorn",
            "graphbook.beta.server.daemon:create_daemon_app",
            "--factory",
            "--host", host,
            "--port", str(port),
            "--log-level", "warning",
        ]
        env = os.environ.copy()
        env["GRAPHBOOK_DAEMON_PORT"] = str(port)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        _write_pid(proc.pid)

        # Wait for server to come up
        for _ in range(50):
            if _is_alive(port):
                print(f"Graphbook daemon started on {host}:{port} (PID {proc.pid})")
                return
            time.sleep(0.1)

        print(f"Graphbook daemon started (PID {proc.pid}), but health check pending...")
    else:
        # Foreground mode
        _write_pid(os.getpid())
        os.environ["GRAPHBOOK_DAEMON_PORT"] = str(port)
        print(f"Starting Graphbook daemon on {host}:{port}...")
        print("Press Ctrl+C to stop.\n")
        import uvicorn
        try:
            uvicorn.run(
                "graphbook.beta.server.daemon:create_daemon_app",
                factory=True,
                host=host,
                port=port,
                log_level="info",
            )
        except KeyboardInterrupt:
            pass
        finally:
            _remove_pid()
            print("\nGraphbook daemon stopped.")


def cmd_run(args: argparse.Namespace) -> None:
    """Run a pipeline managed by the daemon."""
    port = args.port
    script = args.script
    script_args = args.script_args or []

    if not Path(script).exists():
        print(f"Error: Script not found: {script}")
        sys.exit(1)

    # Ensure daemon is running
    if not _is_alive(port):
        print(f"Daemon not running on port {port}. Starting in background...")
        ns = argparse.Namespace(port=port, host="localhost", daemon=True)
        cmd_serve(ns)
        time.sleep(1)

    import httpx

    # Register run with daemon
    run_id = args.name or f"run_{int(time.time())}"

    # Set environment so SDK auto-connects
    env = os.environ.copy()
    env["GRAPHBOOK_SERVER_PORT"] = str(port)
    env["GRAPHBOOK_RUN_ID"] = run_id
    env["GRAPHBOOK_MODE"] = "server"
    env["GRAPHBOOK_FLUSH_INTERVAL"] = str(args.flush_interval)

    cmd = [sys.executable, script] + script_args

    print(f"Starting pipeline: {script} (run_id: {run_id})")
    proc = subprocess.Popen(cmd, env=env)

    try:
        exit_code = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            exit_code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            exit_code = -1

    if exit_code == 0:
        print(f"\nPipeline completed successfully (run_id: {run_id})")
    else:
        print(f"\nPipeline exited with code {exit_code} (run_id: {run_id})")

    # Notify daemon
    try:
        httpx.post(
            f"http://localhost:{port}/events",
            json=[{"type": "run_completed", "data": {"run_id": run_id, "exit_code": exit_code}}],
            timeout=2.0,
        )
    except Exception:
        pass

    sys.exit(exit_code)


def cmd_status(args: argparse.Namespace) -> None:
    """Show daemon status and recent runs."""
    port = args.port

    if not _is_alive(port):
        print("Graphbook daemon is not running.")
        pid = _read_pid()
        if pid:
            print(f"  Stale PID file found: {pid}")
        return

    import httpx

    try:
        health = httpx.get(f"http://localhost:{port}/health", timeout=2.0).json()
        runs = httpx.get(f"http://localhost:{port}/runs", timeout=2.0).json()
    except Exception as e:
        print(f"Error connecting to daemon: {e}")
        return

    print(f"Graphbook daemon: running on port {port}")
    print(f"  Active run: {health.get('active_run', 'none')}")
    print(f"  Total runs: {health.get('total_runs', 0)}")

    run_list = runs.get("runs", [])
    if run_list:
        print(f"\nRecent runs:")
        for r in run_list[-10:]:
            status_icon = {"running": "↻", "completed": "✓", "crashed": "✗", "stopped": "■", "starting": "…"}.get(r["status"], "?")
            print(f"  {status_icon} {r['id']}: {r['status']} | {r['script_path']} | "
                  f"nodes={r.get('node_count', 0)}, errors={r.get('error_count', 0)}")


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop the daemon."""
    port = args.port
    pid = _read_pid()

    if pid and _process_alive(pid):
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to daemon (PID {pid})")
        # Wait for it to die
        for _ in range(30):
            if not _process_alive(pid):
                break
            time.sleep(0.1)
        _remove_pid()
        print("Graphbook daemon stopped.")
    elif _is_alive(port):
        print(f"Daemon is running on port {port} but PID unknown. Use kill manually.")
    else:
        print("Graphbook daemon is not running.")
        _remove_pid()


def cmd_logs(args: argparse.Namespace) -> None:
    """View logs from runs."""
    port = args.port

    if not _is_alive(port):
        print("Graphbook daemon is not running.")
        return

    import httpx

    try:
        params = {"limit": args.limit}
        if args.node:
            params["node"] = args.node

        if args.run:
            url = f"http://localhost:{port}/runs/{args.run}/logs"
        else:
            url = f"http://localhost:{port}/logs"

        resp = httpx.get(url, params=params, timeout=5.0)
        data = resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return

    logs = data.get("logs", [])
    if not logs:
        print("No logs found.")
        return

    for entry in logs:
        node_tag = f"[{entry.get('node', '?')}]" if entry.get("node") else ""
        print(f"  {node_tag} {entry.get('message', '')}")


def cmd_errors(args: argparse.Namespace) -> None:
    """View errors from runs."""
    port = args.port

    if not _is_alive(port):
        print("Graphbook daemon is not running.")
        return

    import httpx

    try:
        if args.run:
            url = f"http://localhost:{port}/runs/{args.run}/errors"
        else:
            url = f"http://localhost:{port}/errors"

        resp = httpx.get(url, timeout=5.0)
        data = resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return

    errors = data.get("errors", [])
    if not errors:
        print("No errors found.")
        return

    for err in errors:
        print(f"\n{'='*60}")
        print(f"Node: {err.get('node_name', '?')}")
        print(f"Type: {err.get('exception_type', '?')}: {err.get('exception_message', '')}")
        tb = err.get("traceback", "")
        if tb:
            print(f"Traceback:\n{tb}")


def cmd_mcp(args: argparse.Namespace) -> None:
    """Print MCP connection config for Claude Code."""
    config = {
        "mcpServers": {
            "graphbook": {
                "command": "graphbook",
                "args": ["mcp-stdio"],
                "env": {},
            }
        }
    }
    print("# Add this to your Claude Code MCP config (~/.claude/mcp.json):")
    print(json.dumps(config, indent=2))


def cmd_mcp_stdio(args: argparse.Namespace) -> None:
    """Run the MCP stdio transport (bridges stdio <-> daemon HTTP)."""
    from graphbook.beta.mcp.stdio import run_stdio_bridge
    run_stdio_bridge(port=args.port)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="graphbook",
        description="Graphbook — Lightweight observability for Python pipelines",
    )
    parser.add_argument("--port", type=int, default=2048, help="Daemon port (default: 2048)")
    subparsers = parser.add_subparsers(dest="command")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start the persistent daemon server")
    p_serve.add_argument("--host", default="localhost", help="Host to bind (default: localhost)")
    p_serve.add_argument("--port", type=int, default=2048, help="Port (default: 2048)")
    p_serve.add_argument("--daemon", "-d", action="store_true", help="Run in background")

    # run
    p_run = subparsers.add_parser("run", help="Run a pipeline managed by the daemon")
    p_run.add_argument("script", help="Path to the Python script")
    p_run.add_argument("--name", help="Run name/ID")
    p_run.add_argument("--port", type=int, default=2048)
    p_run.add_argument("--flush-interval", type=float, default=0.1, help="Seconds between event flushes (default: 0.1)")
    p_run.add_argument("script_args", nargs="*", help="Arguments for the script")

    # status
    p_status = subparsers.add_parser("status", help="Show daemon status")
    p_status.add_argument("--port", type=int, default=2048)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop the daemon")
    p_stop.add_argument("--port", type=int, default=2048)

    # logs
    p_logs = subparsers.add_parser("logs", help="View logs")
    p_logs.add_argument("--run", help="Run ID")
    p_logs.add_argument("--node", help="Filter by node")
    p_logs.add_argument("--limit", type=int, default=100)
    p_logs.add_argument("--port", type=int, default=2048)

    # errors
    p_errors = subparsers.add_parser("errors", help="View errors")
    p_errors.add_argument("--run", help="Run ID")
    p_errors.add_argument("--port", type=int, default=2048)

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Print MCP config for Claude Code")

    # mcp-stdio (internal)
    p_mcp_stdio = subparsers.add_parser("mcp-stdio", help="Run MCP stdio transport")
    p_mcp_stdio.add_argument("--port", type=int, default=2048)

    args = parser.parse_args()

    commands = {
        "serve": cmd_serve,
        "run": cmd_run,
        "status": cmd_status,
        "stop": cmd_stop,
        "logs": cmd_logs,
        "errors": cmd_errors,
        "mcp": cmd_mcp,
        "mcp-stdio": cmd_mcp_stdio,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""Server auto-spawn and lifecycle management."""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

_PID_DIR = Path.home() / ".graphbook"
_PID_FILE = _PID_DIR / "server.pid"


def _is_server_alive(port: int) -> bool:
    """Check if the server is running and healthy."""
    try:
        resp = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _read_pid() -> Optional[int]:
    """Read the server PID from the pid file."""
    try:
        if _PID_FILE.exists():
            return int(_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        pass
    return None


def _write_pid(pid: int) -> None:
    """Write the server PID to the pid file."""
    _PID_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    """Remove the pid file."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is still alive."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def spawn_server(port: int = 2048) -> subprocess.Popen:
    """Spawn the graphbook beta server as a subprocess.

    Args:
        port: Port to bind the server to.

    Returns:
        The subprocess.Popen object.
    """
    cmd = [
        sys.executable, "-m", "uvicorn",
        "graphbook.beta.server.app:create_app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _write_pid(proc.pid)

    # Register cleanup
    def cleanup():
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        _remove_pid()

    atexit.register(cleanup)

    # Wait for server to be ready
    for _ in range(50):
        if _is_server_alive(port):
            return proc
        time.sleep(0.1)

    return proc


def ensure_server(port: int = 2048) -> None:
    """Ensure a graphbook server is running.

    Checks for existing server, restarts if dead.

    Args:
        port: Port to use.
    """
    from graphbook.beta.core.state import get_state
    state = get_state()

    if state._initialized_server:
        return

    # Check if server is already running
    if _is_server_alive(port):
        state._initialized_server = True
        return

    # Check PID file
    pid = _read_pid()
    if pid and _is_process_alive(pid):
        # Process exists but server not responding — give it a moment
        time.sleep(1.0)
        if _is_server_alive(port):
            state._initialized_server = True
            return

    # Spawn new server
    proc = spawn_server(port)
    state.server_process = proc
    state._initialized_server = True


def stop_server() -> None:
    """Stop the managed server process."""
    from graphbook.beta.core.state import get_state
    state = get_state()

    if state.server_process:
        try:
            state.server_process.terminate()
            state.server_process.wait(timeout=5)
        except Exception:
            try:
                state.server_process.kill()
            except Exception:
                pass
        state.server_process = None
        state._initialized_server = False

    pid = _read_pid()
    if pid and _is_process_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    _remove_pid()

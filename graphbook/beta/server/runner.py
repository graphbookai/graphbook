"""Pipeline subprocess management for the graphbook daemon."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional


class PipelineRunner:
    """Manages pipeline subprocesses on behalf of the daemon.

    Starts Python scripts as subprocesses, captures stdout/stderr,
    and reports lifecycle events back to the daemon.
    """

    def __init__(
        self,
        on_started: Optional[Callable[[str], None]] = None,
        on_completed: Optional[Callable[[str, int], None]] = None,
        on_output: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        """Initialize the runner.

        Args:
            on_started: Callback(run_id) when process starts.
            on_completed: Callback(run_id, exit_code) when process exits.
            on_output: Callback(run_id, stream, line) for stdout/stderr lines.
        """
        self._on_started = on_started
        self._on_completed = on_completed
        self._on_output = on_output
        self._processes: dict[str, subprocess.Popen] = {}
        self._monitors: dict[str, threading.Thread] = {}

    def start(
        self,
        run_id: str,
        script_path: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        port: int = 2048,
    ) -> subprocess.Popen:
        """Start a pipeline script as a managed subprocess.

        Args:
            run_id: Unique identifier for this run.
            script_path: Path to the Python script.
            args: Additional command-line arguments for the script.
            env: Extra environment variables.
            port: Daemon port to inject into the environment.

        Returns:
            The subprocess.Popen instance.
        """
        script = Path(script_path).resolve()
        if not script.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        cmd = [sys.executable, str(script)]
        if args:
            cmd.extend(args)

        process_env = os.environ.copy()
        process_env["GRAPHBOOK_SERVER_PORT"] = str(port)
        process_env["GRAPHBOOK_RUN_ID"] = run_id
        process_env["GRAPHBOOK_MODE"] = "server"
        if env:
            process_env.update(env)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
            cwd=str(script.parent),
        )

        self._processes[run_id] = proc

        if self._on_started:
            self._on_started(run_id)

        # Start monitoring thread
        monitor = threading.Thread(
            target=self._monitor_process,
            args=(run_id, proc),
            daemon=True,
        )
        self._monitors[run_id] = monitor
        monitor.start()

        return proc

    def stop(self, run_id: str, timeout: float = 5.0) -> Optional[int]:
        """Stop a running pipeline.

        Args:
            run_id: The run to stop.
            timeout: Seconds to wait before killing.

        Returns:
            The exit code, or None if not found.
        """
        proc = self._processes.get(run_id)
        if proc is None:
            return None

        try:
            proc.terminate()
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

        return proc.returncode

    def is_running(self, run_id: str) -> bool:
        """Check if a pipeline is still running."""
        proc = self._processes.get(run_id)
        return proc is not None and proc.poll() is None

    def _monitor_process(self, run_id: str, proc: subprocess.Popen) -> None:
        """Monitor a subprocess, streaming output and detecting exit."""
        stdout_thread = threading.Thread(
            target=self._stream_output,
            args=(run_id, proc.stdout, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._stream_output,
            args=(run_id, proc.stderr, "stderr"),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        # Wait for process to finish
        exit_code = proc.wait()

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        if self._on_completed:
            self._on_completed(run_id, exit_code)

        # Clean up
        self._processes.pop(run_id, None)
        self._monitors.pop(run_id, None)

    def _stream_output(self, run_id: str, stream: Any, name: str) -> None:
        """Read lines from a subprocess stream and forward to callback."""
        if stream is None:
            return
        try:
            for raw_line in stream:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if self._on_output:
                    self._on_output(run_id, name, line)
        except Exception:
            pass

    def stop_all(self) -> None:
        """Stop all running pipelines."""
        for run_id in list(self._processes.keys()):
            self.stop(run_id)

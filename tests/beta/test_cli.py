"""Tests for the CLI module."""

from __future__ import annotations

import argparse
import json

import pytest

from graphbook.beta.cli import cmd_mcp


class TestCLI:
    """Tests for CLI commands."""

    def test_mcp_outputs_valid_json(self, capsys: pytest.CaptureFixture) -> None:
        """graphbook mcp should output valid JSON config."""
        args = argparse.Namespace()
        cmd_mcp(args)
        captured = capsys.readouterr()
        # The output includes a comment line, then JSON
        lines = captured.out.strip().split("\n")
        # First line is a comment
        assert lines[0].startswith("#")
        # Rest is JSON
        json_str = "\n".join(lines[1:])
        config = json.loads(json_str)
        assert "mcpServers" in config
        assert "graphbook" in config["mcpServers"]
        assert config["mcpServers"]["graphbook"]["command"] == "graphbook"
        assert "mcp-stdio" in config["mcpServers"]["graphbook"]["args"]


class TestRunnerModule:
    """Tests for the PipelineRunner."""

    def test_runner_import(self) -> None:
        """PipelineRunner should be importable."""
        from graphbook.beta.server.runner import PipelineRunner
        runner = PipelineRunner()
        assert runner is not None

    def test_runner_not_running(self) -> None:
        """is_running should return False for unknown run IDs."""
        from graphbook.beta.server.runner import PipelineRunner
        runner = PipelineRunner()
        assert runner.is_running("nonexistent") is False

    def test_runner_stop_unknown(self) -> None:
        """stop() should return None for unknown run IDs."""
        from graphbook.beta.server.runner import PipelineRunner
        runner = PipelineRunner()
        assert runner.stop("nonexistent") is None

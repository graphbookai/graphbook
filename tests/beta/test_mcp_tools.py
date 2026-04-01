"""Tests for MCP tools."""

from __future__ import annotations

import pytest

from graphbook.beta.core.state import SessionState


class TestMCPObservationTools:
    """Tests for MCP observation tools against in-process state."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    @pytest.mark.asyncio
    async def test_get_description(self) -> None:
        """Should return workflow description and node docstrings."""
        from graphbook.beta.mcp.tools import get_description
        from graphbook.beta.core.state import get_state
        from graphbook.beta.core.decorators import fn

        @fn()
        def my_func():
            """A documented function."""
            pass

        my_func()  # Node registers on first execution

        state = get_state()
        state.workflow_description = "Test workflow"

        result = await get_description(server_url="http://localhost:19999")
        assert result["workflow_description"] == "Test workflow"
        assert any("A documented function" in (v or "") for v in result["node_descriptions"].values())

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(self) -> None:
        """Should return error when node not found."""
        from graphbook.beta.mcp.tools import get_metrics
        result = await get_metrics("nonexistent_node")
        assert "error" in result


class TestMCPActionTools:
    """Tests for MCP action tools."""

    @pytest.mark.asyncio
    async def test_get_source_code_not_found(self) -> None:
        """Should return error for nonexistent file."""
        from graphbook.beta.mcp.tools import get_source_code
        result = await get_source_code("/nonexistent/path.py")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_source_code_reads_file(self, tmp_path) -> None:
        """Should read an existing file."""
        from graphbook.beta.mcp.tools import get_source_code
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        result = await get_source_code(str(f))
        assert result["content"] == "print('hello')"

    @pytest.mark.asyncio
    async def test_write_source_code_full(self, tmp_path) -> None:
        """Should write full content to a file."""
        from graphbook.beta.mcp.tools import write_source_code
        f = tmp_path / "test.py"
        f.write_text("old content")
        result = await write_source_code(str(f), content="new content")
        assert result["status"] == "written"
        assert f.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_write_source_code_patches(self, tmp_path) -> None:
        """Should apply patches to a file."""
        from graphbook.beta.mcp.tools import write_source_code
        f = tmp_path / "test.py"
        f.write_text("batch_size = 64\nlr = 0.01")
        result = await write_source_code(
            str(f),
            patches=[{"old": "batch_size = 64", "new": "batch_size = 16"}],
        )
        assert result["status"] == "patched"
        assert "batch_size = 16" in f.read_text()
        assert "lr = 0.01" in f.read_text()

    @pytest.mark.asyncio
    async def test_write_source_code_patch_not_found(self, tmp_path) -> None:
        """Should error when patch target not found."""
        from graphbook.beta.mcp.tools import write_source_code
        f = tmp_path / "test.py"
        f.write_text("hello world")
        result = await write_source_code(
            str(f),
            patches=[{"old": "nonexistent text", "new": "replacement"}],
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_write_source_code_no_args(self, tmp_path) -> None:
        """Should error when neither content nor patches provided."""
        from graphbook.beta.mcp.tools import write_source_code
        f = tmp_path / "test.py"
        f.write_text("hello")
        result = await write_source_code(str(f))
        assert "error" in result


class TestMCPDispatcher:
    """Tests for the MCP tool dispatcher."""

    def setup_method(self) -> None:
        SessionState.reset_singleton()

    @pytest.mark.asyncio
    async def test_unknown_tool(self) -> None:
        """Should return error for unknown tool names."""
        from graphbook.beta.mcp.server import handle_tool_call
        result = await handle_tool_call("nonexistent_tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_run_history_no_daemon(self) -> None:
        """Should return error when daemon not available."""
        from graphbook.beta.mcp.tools import get_run_history
        result = await get_run_history("http://localhost:19999")
        assert "error" in result

"""Tests for the CLI functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flowwatch.cli import _import_target, app

runner = CliRunner()


class TestImportTarget:
    """Tests for the _import_target function."""

    def test_import_module_by_name(self) -> None:
        """Should be able to import a standard library module."""
        # This should not raise
        _import_target("json")

    def test_import_file_by_path(self) -> None:
        """Should be able to import a .py file by path."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("TEST_VAR = 42\n")
            f.flush()

            # Should not raise
            _import_target(f.name)

    def test_import_nonexistent_file_exits(self) -> None:
        """Should exit with code 1 for nonexistent file."""
        import typer

        with pytest.raises(typer.Exit) as exc_info:
            _import_target("/nonexistent/path/to/file.py")
        assert exc_info.value.exit_code == 1

    def test_import_nonexistent_module_raises(self) -> None:
        """Should raise ImportError for nonexistent module."""
        with pytest.raises(ModuleNotFoundError):
            _import_target("nonexistent_module_xyz_12345")


class TestRunCommand:
    """Tests for the 'run' CLI command.

    Note: Typer with a single command makes it the default, so we invoke
    directly with the target as the first argument, not "run target".
    """

    def test_run_shows_help(self) -> None:
        """Run command should show help with --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "FlowWatch" in result.output

    def test_run_without_target_shows_usage(self) -> None:
        """Run without target should show usage/help."""
        result = runner.invoke(app, [])
        # Typer shows usage when no args provided
        assert result.exit_code == 0 or "Usage" in result.output

    def test_run_invalid_target_exits(self) -> None:
        """Run with invalid target should exit with error."""
        result = runner.invoke(app, ["nonexistent_module_xyz"])
        assert result.exit_code == 1
        assert "Error importing target" in result.output

    def test_run_no_handlers_exits(self) -> None:
        """Run with module that has no handlers should exit with error."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            # Empty module with no handlers
            f.write("# Empty module\n")
            f.flush()

            result = runner.invoke(app, [f.name])
            assert result.exit_code == 1
            assert "No FlowWatch handlers found" in result.output

    @patch("flowwatch.cli.run_default_app")
    def test_run_with_handlers_starts_watcher(
        self, mock_run: MagicMock
    ) -> None:
        """Run with valid handlers should start the watcher."""
        from flowwatch.decorators import default_app

        # Clear any existing handlers from default_app
        default_app._handlers.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            resolved_tmpdir = Path(tmpdir).resolve()
            # Create a module with handlers
            module_path = Path(tmpdir) / "test_handlers.py"
            module_path.write_text(f"""
from flowwatch import on_created, FileEvent

@on_created("{resolved_tmpdir}", pattern="*.txt")
def handler(event: FileEvent) -> None:
    pass
""")

            result = runner.invoke(app, [str(module_path)])
            # Should have started (mock prevents actual run)
            mock_run.assert_called_once()

            # Clean up the handler we added
            default_app._handlers.clear()

    def test_run_debounce_option(self) -> None:
        """Run should accept --debounce option."""
        result = runner.invoke(app, ["--help"])
        assert "--debounce" in result.output
        assert "-d" in result.output

    def test_run_max_workers_option(self) -> None:
        """Run should accept --max-workers option."""
        result = runner.invoke(app, ["--help"])
        assert "--max-workers" in result.output
        assert "-w" in result.output

    def test_run_recursive_option(self) -> None:
        """Run should accept --recursive/--no-recursive option."""
        result = runner.invoke(app, ["--help"])
        assert "--recursive" in result.output
        assert "--no-recursive" in result.output

    def test_run_log_level_option(self) -> None:
        """Run should accept --log-level option."""
        result = runner.invoke(app, ["--help"])
        assert "--log-level" in result.output
        assert "-l" in result.output

    def test_run_json_logs_option(self) -> None:
        """Run should accept --json-logs option."""
        result = runner.invoke(app, ["--help"])
        assert "--json-logs" in result.output


class TestMainFunction:
    """Tests for the main() entry point."""

    def test_main_invokes_typer_app(self) -> None:
        """main() should invoke the Typer app."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "FlowWatch" in result.output


"""Pytest configuration and fixtures for FlowWatch tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from flowwatch import FlowWatchApp


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for file watching tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def watch_app() -> FlowWatchApp:
    """Create a fresh FlowWatchApp instance for testing."""
    return FlowWatchApp(name="test-app", debounce=0.1, max_workers=2)


@pytest.fixture
def temp_file(temp_dir: Path) -> Path:
    """Create a temporary file in the temp directory."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("initial content")
    return file_path


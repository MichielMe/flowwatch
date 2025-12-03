# src/flowwatch/__init__.py
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .app import FileEvent, FlowWatchApp
from .decorators import default_app, on_any, on_created, on_deleted, on_modified, run

try:
    __version__ = version("flowwatch")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

# Backwards-compatible alias
run_flowwatch = run

__all__ = [
    "FileEvent",
    "FlowWatchApp",
    "default_app",
    "on_created",
    "on_modified",
    "on_deleted",
    "on_any",
    "run",
    "run_flowwatch",
    "__version__",
]

# src/flowwatch/__init__.py
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .app import FileEvent, FlowWatchApp, JsonFormatter
from .decorators import default_app, on_any, on_created, on_deleted, on_modified, run

try:
    __version__ = version("flowwatch")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.1.1"

# Backwards-compatible alias
run_flowwatch = run


def run_with_dashboard(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    pretty: bool = True,
) -> None:
    """
    Run the default FlowWatch app with the web dashboard.

    This combines the file watcher with a real-time web UI
    showing all events as they happen.

    Parameters
    ----------
    host:
        Host to bind the dashboard server to.
    port:
        Port for the dashboard server.
    open_browser:
        Whether to automatically open the browser.
    pretty:
        Whether to show the Rich console output.
    """
    from .dashboard import run_dashboard

    run_dashboard(default_app, host=host, port=port, open_browser=open_browser)
    run(pretty=pretty)


def stop_dashboard(timeout: float = 5.0) -> None:
    """
    Stop the global dashboard server gracefully.

    Parameters
    ----------
    timeout:
        Maximum time to wait for server shutdown in seconds.
    """
    from .dashboard import stop_dashboard as _stop_dashboard

    _stop_dashboard(timeout=timeout)


__all__ = [
    "FileEvent",
    "FlowWatchApp",
    "JsonFormatter",
    "__version__",
    "default_app",
    "on_any",
    "on_created",
    "on_deleted",
    "on_modified",
    "run",
    "run_flowwatch",
    "run_with_dashboard",
    "stop_dashboard",
]

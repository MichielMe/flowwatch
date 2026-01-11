"""FlowWatch Dashboard - Real-time web UI for file watching events."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import threading
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from .app import FileEvent, FlowWatchApp


def _load_dashboard_html() -> str:
    """Load the dashboard HTML from the static folder."""
    try:
        return (
            resources.files(__package__).joinpath("static/dashboard.html").read_text()
        )
    except (TypeError, FileNotFoundError, OSError):
        # Fallback if resources don't work (e.g., editable install)
        from pathlib import Path

        static_path = Path(__file__).parent / "static" / "dashboard.html"
        return static_path.read_text()


# Check if dashboard dependencies are available
try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, Response, StreamingResponse
    from starlette.routing import Route

    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False


@dataclass
class EventRecord:
    """A recorded event for display in the dashboard."""

    timestamp: str
    change_type: str
    path: str
    handler: str
    pattern: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "timestamp": self.timestamp,
            "change_type": self.change_type,
            "path": self.path,
            "handler": self.handler,
            "pattern": self.pattern,
        }


@dataclass
class DashboardState:
    """Shared state for the dashboard."""

    events: deque[EventRecord] = field(default_factory=lambda: deque(maxlen=100))
    stats: dict[str, int] = field(
        default_factory=lambda: {"added": 0, "modified": 0, "deleted": 0, "total": 0}
    )
    handlers: list[dict[str, str]] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    subscribers: set[asyncio.Queue[str]] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    start_time: float = field(default_factory=lambda: datetime.now(tz=UTC).timestamp())

    def add_event(self, event: EventRecord) -> None:
        with self.lock:
            self.events.appendleft(event)
            self.stats[event.change_type] += 1
            self.stats["total"] += 1

    def broadcast(self, data: dict[str, object]) -> None:
        """Broadcast data to all SSE subscribers."""
        message = f"data: {json.dumps(data)}\n\n"
        for queue in list(self.subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(message)

    def reset(self) -> None:
        """Reset state for reuse (useful in tests)."""
        with self.lock:
            self.events.clear()
            self.stats = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
            self.handlers.clear()
            self.roots.clear()
            self.subscribers.clear()
            self.start_time = datetime.now(tz=UTC).timestamp()


# Global dashboard state - used for backwards compatibility
# For production use, prefer creating DashboardState instances explicitly
_state = DashboardState()


def create_event_hook(
    app: FlowWatchApp, state: DashboardState | None = None
) -> DashboardState:
    """
    Create a hook that captures events for the dashboard.

    Parameters
    ----------
    app:
        The FlowWatchApp to hook into.
    state:
        Optional DashboardState instance. If not provided, uses global state.

    Returns
    -------
    DashboardState:
        The state instance being used.
    """
    if state is None:
        state = _state
        state.reset()  # Reset global state for clean start

    # Store original _submit method
    original_submit = app._submit

    def _hooked_submit(handler: object, event: FileEvent) -> None:
        # Record the event
        record = EventRecord(
            timestamp=datetime.now(tz=UTC).strftime("%H:%M:%S.%f")[:-3],
            change_type=event.change.name,
            path=str(event.path),
            handler=getattr(getattr(handler, "func", handler), "__name__", str(handler)),
            pattern=event.pattern,
        )
        assert state is not None  # For type checker
        state.add_event(record)
        state.broadcast({"type": "event", "event": record.to_dict()})

        # Call original
        original_submit(handler, event)  # type: ignore[arg-type]

    app._submit = _hooked_submit  # type: ignore[method-assign]

    # Populate handler info
    state.handlers = [
        {
            "name": getattr(h.func, "__name__", str(h.func)),
            "root": str(h.root),
            "events": ", ".join(e.name for e in h.events),
            "pattern": h.pattern or "*",
            "priority": str(h.priority),
        }
        for h in app.handlers
    ]
    state.roots = [str(r) for r in sorted({h.root for h in app.handlers})]

    return state


# Dashboard HTML is loaded from static/dashboard.html
_DASHBOARD_HTML_CACHE: str | None = None


def _get_dashboard_html() -> str:
    """Get dashboard HTML, caching after first load."""
    global _DASHBOARD_HTML_CACHE  # noqa: PLW0603
    if _DASHBOARD_HTML_CACHE is None:
        _DASHBOARD_HTML_CACHE = _load_dashboard_html()
    return _DASHBOARD_HTML_CACHE


def _create_dashboard_app(state: DashboardState | None = None) -> Starlette:
    """
    Create the Starlette dashboard application.

    Parameters
    ----------
    state:
        Optional DashboardState instance. If not provided, uses global state.
    """
    if not DASHBOARD_AVAILABLE:
        msg = (
            "Dashboard dependencies not installed. "
            "Install with: pip install flowwatch[dashboard]"
        )
        raise ImportError(msg)

    if state is None:
        state = _state

    async def homepage(_request: object) -> HTMLResponse:
        return HTMLResponse(_get_dashboard_html())

    async def api_state(_request: object) -> Response:
        with state.lock:
            data = {
                "stats": state.stats,
                "events": [e.to_dict() for e in state.events],
                "handlers": state.handlers,
                "roots": state.roots,
            }
        return Response(
            content=json.dumps(data),
            media_type="application/json",
        )

    async def api_events(_request: object) -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[bytes, None]:
            queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
            state.subscribers.add(queue)
            try:
                while True:
                    message = await queue.get()
                    yield message.encode()
            finally:
                state.subscribers.discard(queue)

        return StreamingResponse(
            content=event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def api_health(_request: object) -> Response:
        """Health check endpoint for container orchestration."""
        uptime = datetime.now(tz=UTC).timestamp() - state.start_time
        with state.lock:
            data = {
                "status": "healthy",
                "uptime_seconds": round(uptime, 2),
                "handlers_count": len(state.handlers),
                "roots_count": len(state.roots),
                "events_processed": state.stats["total"],
            }
        return Response(
            content=json.dumps(data),
            media_type="application/json",
        )

    async def api_file(request: Request) -> Response:
        """Return file contents (truncated) for preview."""
        from pathlib import Path

        file_path = request.query_params.get("path")
        if not file_path:
            return Response(
                content=json.dumps({"error": "No path provided"}),
                status_code=400,
                media_type="application/json",
            )

        path = Path(file_path).resolve()

        # Security: Only allow files within watched roots to prevent path traversal
        watched_roots = [Path(r).resolve() for r in state.roots]
        if not watched_roots or not any(
            path == root or root in path.parents for root in watched_roots
        ):
            return Response(
                content=json.dumps(
                    {"error": "Access denied: file outside watched directories"}
                ),
                status_code=403,
                media_type="application/json",
            )

        if not path.exists():
            return Response(
                content=json.dumps({"error": "File not found"}),
                status_code=404,
                media_type="application/json",
            )

        if not path.is_file():
            return Response(
                content=json.dumps({"error": "Not a file"}),
                status_code=400,
                media_type="application/json",
            )

        stat = path.stat()
        size = stat.st_size
        modified = stat.st_mtime

        max_preview_bytes = 1_000_000  # ~1MB
        read_limit = min(size, max_preview_bytes)

        try:
            with path.open("rb") as f:
                raw = f.read(read_limit)
        except OSError as exc:  # pragma: no cover - IO errors
            return Response(
                content=json.dumps({"error": str(exc)}),
                status_code=500,
                media_type="application/json",
            )

        is_probably_binary = b"\0" in raw
        truncated = size > read_limit

        if is_probably_binary:
            return Response(
                content=json.dumps(
                    {
                        "is_binary": True,
                        "size": size,
                        "modified": modified,
                        "truncated": truncated,
                        "error": "Binary file preview not available",
                    }
                ),
                media_type="application/json",
            )

        content = raw.decode("utf-8", errors="replace")
        return Response(
            content=json.dumps(
                {
                    "content": content,
                    "size": size,
                    "modified": modified,
                    "is_binary": False,
                    "truncated": truncated,
                }
            ),
            media_type="application/json",
        )

    routes = [
        Route("/", homepage),
        Route("/api/state", api_state),
        Route("/api/events", api_events),
        Route("/api/health", api_health),
        Route("/health", api_health),  # Alias for k8s probes
        Route("/api/file", api_file),
    ]

    return Starlette(routes=routes)


@dataclass
class DashboardServer:
    """
    Manages the dashboard server lifecycle with graceful shutdown support.

    This class wraps the uvicorn server and provides methods for
    starting, stopping, and checking the server status.
    """

    host: str = "127.0.0.1"
    port: int = 8765
    _server: Any = field(default=None, repr=False)  # uvicorn.Server when running
    _thread: threading.Thread | None = field(default=None, repr=False)
    _state: DashboardState = field(default_factory=DashboardState, repr=False)

    @property
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def url(self) -> str:
        """Get the URL where the dashboard is accessible."""
        return f"http://{self.host}:{self.port}"

    @property
    def state(self) -> DashboardState:
        """Get the dashboard state instance."""
        return self._state

    def start(
        self,
        app: FlowWatchApp,
        *,
        open_browser: bool = True,
    ) -> None:
        """
        Start the dashboard server.

        Parameters
        ----------
        app:
            The FlowWatchApp instance to monitor.
        open_browser:
            Whether to open the browser automatically.
        """
        if self.is_running:
            return  # Already running

        if not DASHBOARD_AVAILABLE:
            msg = (
                "Dashboard dependencies not installed. "
                "Install with: pip install flowwatch[dashboard]"
            )
            raise ImportError(msg)

        import uvicorn

        # Hook into the app to capture events
        create_event_hook(app, self._state)

        dashboard = _create_dashboard_app(self._state)

        if open_browser:
            # Open browser after a short delay to let server start
            threading.Timer(1.0, lambda: webbrowser.open(self.url)).start()

        # Create uvicorn server
        config = uvicorn.Config(
            dashboard,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        # Run in background thread
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        # Register shutdown handler
        atexit.register(self.stop)

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the dashboard server gracefully.

        Parameters
        ----------
        timeout:
            Maximum time to wait for server shutdown in seconds.
        """
        if self._server is not None:
            self._server.should_exit = True

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        self._server = None
        self._thread = None

        # Unregister atexit handler to avoid double-stop
        with contextlib.suppress(Exception):
            atexit.unregister(self.stop)


# Global server instance for simple usage
_dashboard_server: DashboardServer | None = None


def run_dashboard(
    app: FlowWatchApp,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> DashboardServer:
    """
    Run the FlowWatch dashboard server.

    This starts a web server that shows real-time file events.

    Parameters
    ----------
    app:
        The FlowWatchApp instance to monitor.
    host:
        Host to bind the server to.
    port:
        Port to bind the server to.
    open_browser:
        Whether to open the browser automatically.

    Returns
    -------
    DashboardServer:
        The server instance, which can be used for graceful shutdown.
    """
    global _dashboard_server  # noqa: PLW0603

    if _dashboard_server is not None and _dashboard_server.is_running:
        _dashboard_server.stop()

    _dashboard_server = DashboardServer(host=host, port=port)
    _dashboard_server.start(app, open_browser=open_browser)

    return _dashboard_server


def stop_dashboard(timeout: float = 5.0) -> None:
    """
    Stop the global dashboard server gracefully.

    Parameters
    ----------
    timeout:
        Maximum time to wait for server shutdown in seconds.
    """
    global _dashboard_server  # noqa: PLW0603

    if _dashboard_server is not None:
        _dashboard_server.stop(timeout=timeout)
        _dashboard_server = None

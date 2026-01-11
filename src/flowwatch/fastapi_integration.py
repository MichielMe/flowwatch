"""FlowWatch FastAPI Integration - Mount the dashboard in your FastAPI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import FlowWatchApp

# Check if FastAPI is available
try:
    from fastapi import APIRouter
    from fastapi.responses import HTMLResponse, StreamingResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


def create_dashboard_routes(
    app: FlowWatchApp,
    *,
    prefix: str = "",
) -> APIRouter:
    """
    Create a FastAPI router with FlowWatch dashboard routes.

    This allows you to mount the FlowWatch dashboard in your existing
    FastAPI application at any prefix you choose.

    Parameters
    ----------
    app:
        The FlowWatchApp instance to monitor.
    prefix:
        URL prefix for all routes (e.g., "/flowwatch").
        Leave empty if you're using include_router with a prefix.

    Returns
    -------
    APIRouter:
        A FastAPI router with all dashboard routes.

    Example
    -------
    ```python
    from fastapi import FastAPI
    from flowwatch import FlowWatchApp
    from flowwatch.fastapi_integration import create_dashboard_routes

    fastapi_app = FastAPI()
    flowwatch_app = FlowWatchApp()

    # Mount dashboard at /flowwatch/
    fastapi_app.include_router(
        create_dashboard_routes(flowwatch_app),
        prefix="/flowwatch",
    )

    @flowwatch_app.on_created("./watch_dir")
    def handle_new_file(event):
        print(f"New file: {event.path}")
    ```
    """
    if not FASTAPI_AVAILABLE:
        msg = (
            "FastAPI integration requires FastAPI. "
            "Install with: pip install flowwatch[fastapi]"
        )
        raise ImportError(msg)

    from .dashboard import (
        DASHBOARD_AVAILABLE,
        DashboardState,
        _get_dashboard_html,
        create_event_hook,
    )

    if not DASHBOARD_AVAILABLE:
        msg = (
            "Dashboard dependencies not installed. "
            "Install with: pip install flowwatch[fastapi]"
        )
        raise ImportError(msg)

    import asyncio
    import json
    from collections.abc import AsyncGenerator
    from datetime import UTC, datetime
    from pathlib import Path

    from fastapi import Query, Response

    # Create state for this router instance
    state = DashboardState()

    # Hook into the FlowWatch app to capture events
    create_event_hook(app, state)

    router = APIRouter(prefix=prefix)

    @router.get("/", response_class=HTMLResponse)
    async def dashboard_home() -> HTMLResponse:
        """Serve the dashboard HTML page."""
        return HTMLResponse(_get_dashboard_html())

    @router.get("/state")
    async def get_state() -> Response:
        """Get current dashboard state including stats, events, and handlers."""
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

    @router.get("/events")
    async def get_events() -> StreamingResponse:
        """Server-Sent Events stream for real-time updates."""

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

    @router.get("/health")
    async def get_health() -> Response:
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

    @router.get("/file")
    async def get_file(
        path: str | None = Query(default=None, description="File path to preview"),
    ) -> Response:
        """Return file contents (truncated) for preview."""
        if not path:
            return Response(
                content=json.dumps({"error": "No path provided"}),
                status_code=400,
                media_type="application/json",
            )

        file_path = Path(path).resolve()

        # Security: Only allow files within watched roots
        watched_roots = [Path(r).resolve() for r in state.roots]
        if not watched_roots or not any(
            file_path == root or root in file_path.parents for root in watched_roots
        ):
            return Response(
                content=json.dumps(
                    {"error": "Access denied: file outside watched directories"}
                ),
                status_code=403,
                media_type="application/json",
            )

        if not file_path.exists():
            return Response(
                content=json.dumps({"error": "File not found"}),
                status_code=404,
                media_type="application/json",
            )

        if not file_path.is_file():
            return Response(
                content=json.dumps({"error": "Not a file"}),
                status_code=400,
                media_type="application/json",
            )

        stat = file_path.stat()
        size = stat.st_size
        modified = stat.st_mtime

        max_preview_bytes = 1_000_000  # ~1MB
        read_limit = min(size, max_preview_bytes)

        try:
            with file_path.open("rb") as f:
                raw = f.read(read_limit)
        except OSError as exc:
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

    return router

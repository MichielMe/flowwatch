#!/usr/bin/env python3
"""
FastAPI Integration Example
===========================

Demonstrates how to mount FlowWatch's dashboard in your FastAPI application:
- Real-time event streaming via SSE
- Dashboard UI at a custom prefix
- Integration with FastAPI's lifespan management

Run with: uv run examples/fastapi_integration.py

Requires: uv add flowwatch --extra fastapi
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from flowwatch import (
    FileEvent,
    FlowWatchApp,
    create_dashboard_routes,
    on_created,
    on_deleted,
    on_modified,
)

# Watch directories
WATCH_DIR = Path(__file__).parent.parent / "watch_inbox"
WATCH_DIR.mkdir(exist_ok=True)

# Create FlowWatch app
flowwatch = FlowWatchApp()


# ============================================================================
# File Handlers - use app= to register with our FlowWatchApp instance
# ============================================================================


@on_created(str(WATCH_DIR), pattern="*.txt", app=flowwatch)
def on_txt_created(event: FileEvent) -> None:
    print(f"✨ New text file: {event.path.name}")


@on_modified(str(WATCH_DIR), pattern="*.txt", app=flowwatch)
def on_txt_modified(event: FileEvent) -> None:
    print(f"📝 Modified: {event.path.name}")


@on_deleted(str(WATCH_DIR), pattern="*.txt", app=flowwatch)
def on_txt_deleted(event: FileEvent) -> None:
    print(f"🗑️  Deleted: {event.path.name}")


@on_created(str(WATCH_DIR), pattern="*.json", app=flowwatch)
def on_json_created(event: FileEvent) -> None:
    print(f"📋 New JSON: {event.path.name}")


# ============================================================================
# FastAPI App with Lifespan
# ============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage FlowWatch lifecycle with FastAPI."""
    # Start watching on startup
    flowwatch.start()
    print(f"\n🔍 Watching: {WATCH_DIR.absolute()}")
    print("📊 Dashboard: http://localhost:8000/flowwatch/\n")
    yield
    # Stop watching on shutdown
    flowwatch.stop()


app = FastAPI(
    title="FlowWatch FastAPI Example",
    description="Example app with integrated FlowWatch dashboard",
    lifespan=lifespan,
)

# Mount FlowWatch dashboard at /flowwatch/
app.include_router(
    create_dashboard_routes(flowwatch),
    prefix="/flowwatch",
    tags=["FlowWatch"],
)


# ============================================================================
# Your Own Routes
# ============================================================================


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with links."""
    return {
        "message": "FlowWatch FastAPI Integration Example",
        "dashboard": "/flowwatch/",
        "health": "/flowwatch/health",
    }


@app.get("/status")
async def status() -> dict[str, object]:
    """Get FlowWatch status."""
    return {
        "running": flowwatch.is_running,
        "handlers": len(flowwatch.handlers),
        "watch_dir": str(WATCH_DIR.absolute()),
    }

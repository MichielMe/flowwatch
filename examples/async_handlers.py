#!/usr/bin/env python3
"""
Async Handlers Example
======================

Demonstrates FlowWatch's native async handler support:
- Sync handlers run in a thread pool
- Async handlers run in a dedicated event loop
- Both can be mixed freely on the same patterns

Run with: uv run examples/async_handlers.py
"""

import asyncio
from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run

# Watch directory (created automatically if it doesn't exist)
WATCH_DIR = Path(__file__).parent.parent / "watch_inbox"
WATCH_DIR.mkdir(exist_ok=True)


# ============================================================================
# Sync handlers (run in thread pool)
# ============================================================================


@on_created(str(WATCH_DIR), pattern="*.txt")
def handle_txt_sync(event: FileEvent) -> None:
    """Sync handler for text files."""
    print(f"[sync] ✨ New text file: {event.path.name}")


@on_modified(str(WATCH_DIR), pattern="*.txt")
def handle_txt_modified(event: FileEvent) -> None:
    """Sync handler for modified text files."""
    print(f"[sync] 📝 Modified: {event.path.name}")


# ============================================================================
# Async handlers (run in dedicated event loop)
# ============================================================================


@on_created(str(WATCH_DIR), pattern="*.json")
async def handle_json_async(event: FileEvent) -> None:
    """Async handler - simulates an API call."""
    print(f"[async] 📨 Processing JSON: {event.path.name}")
    # Simulate async I/O (API call, database write, etc.)
    await asyncio.sleep(0.5)
    print(f"[async] ✅ Done processing: {event.path.name}")


@on_modified(str(WATCH_DIR), pattern="*.json")
async def handle_json_modified(event: FileEvent) -> None:
    """Async handler for modified JSON files."""
    print(f"[async] 📝 JSON modified: {event.path.name}")
    await asyncio.sleep(0.1)
    content = event.path.read_text()
    print(f"[async] 📊 Size: {len(content)} bytes")


# ============================================================================
# Mixed: Both sync AND async on the same pattern
# ============================================================================


@on_created(str(WATCH_DIR), pattern="*.py")
def handle_py_sync(event: FileEvent) -> None:
    """Sync handler for Python files - runs immediately."""
    print(f"[sync] 🐍 New Python file: {event.path.name}")


@on_created(str(WATCH_DIR), pattern="*.py")
async def handle_py_async(event: FileEvent) -> None:
    """Async handler for Python files - runs concurrently with sync."""
    await asyncio.sleep(0.2)
    lines = event.path.read_text().count("\n") + 1
    print(f"[async] 📏 Python file has {lines} lines")


@on_deleted(str(WATCH_DIR), pattern="*.py")
async def handle_py_deleted(event: FileEvent) -> None:
    """Async handler for deleted Python files."""
    print(f"[async] 🗑️  Python file deleted: {event.path.name}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FlowWatch Async Handlers Example")
    print("=" * 60)
    print(f"\n📁 Watch directory: {WATCH_DIR.absolute()}")
    print("\nHandler types:")
    print("  • .txt files  → sync handler")
    print("  • .json files → async handler (simulates API call)")
    print("  • .py files   → BOTH sync and async handlers")
    print("\nPress Ctrl+C to stop.\n")
    run()

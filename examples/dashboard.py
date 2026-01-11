#!/usr/bin/env python3
"""
Dashboard Example
=================

Demonstrates FlowWatch's real-time web dashboard:
- Live event streaming via Server-Sent Events (SSE)
- Event statistics and file preview
- Multiple watch directories

Run with: uv run examples/dashboard.py

Requires: uv add flowwatch --extra dashboard
"""

from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run_with_dashboard

# Watch directories (created automatically if they don't exist)
INBOX_DIR = Path(__file__).parent.parent / "watch_inbox"
DATA_DIR = Path(__file__).parent.parent / "watch_data"
INBOX_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


# ============================================================================
# Handlers for watch_inbox/
# ============================================================================


@on_created(str(INBOX_DIR), pattern="*.txt")
def inbox_txt_created(event: FileEvent) -> None:
    print(f"[inbox] ✨ New: {event.path.name}")


@on_modified(str(INBOX_DIR), pattern="*.txt")
def inbox_txt_modified(event: FileEvent) -> None:
    print(f"[inbox] 📝 Modified: {event.path.name}")


@on_deleted(str(INBOX_DIR), pattern="*.txt")
def inbox_txt_deleted(event: FileEvent) -> None:
    print(f"[inbox] 🗑️  Deleted: {event.path.name}")


@on_created(str(INBOX_DIR), pattern="*.json")
def inbox_json_created(event: FileEvent) -> None:
    print(f"[inbox] 📋 New JSON: {event.path.name}")


@on_created(str(INBOX_DIR), pattern="*.py")
def inbox_py_created(event: FileEvent) -> None:
    print(f"[inbox] 🐍 New Python: {event.path.name}")


# ============================================================================
# Handlers for watch_data/
# ============================================================================


@on_created(str(DATA_DIR), pattern="*.txt")
def data_txt_created(event: FileEvent) -> None:
    print(f"[data] ✨ New: {event.path.name}")


@on_modified(str(DATA_DIR), pattern="*.txt")
def data_txt_modified(event: FileEvent) -> None:
    print(f"[data] 📝 Modified: {event.path.name}")


@on_deleted(str(DATA_DIR), pattern="*.txt")
def data_txt_deleted(event: FileEvent) -> None:
    print(f"[data] 🗑️  Deleted: {event.path.name}")


@on_created(str(DATA_DIR), pattern="*.json")
def data_json_created(event: FileEvent) -> None:
    print(f"[data] 📋 New JSON: {event.path.name}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FlowWatch Dashboard Example")
    print("=" * 60)
    print("\n📁 Watch directories:")
    print(f"   • {INBOX_DIR.absolute()}")
    print(f"   • {DATA_DIR.absolute()}")
    print("\n🌐 Dashboard will open at http://127.0.0.1:8765")
    print("\nPress Ctrl+C to stop.\n")
    run_with_dashboard(port=8765, open_browser=True)

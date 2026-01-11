#!/usr/bin/env python3
"""
Basic FlowWatch Example
=======================

Demonstrates simple file watching with sync handlers for:
- File creation (@on_created)
- File modification (@on_modified)
- File deletion (@on_deleted)

Run with: uv run examples/basic.py
"""

from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run

# Watch directory (created automatically if it doesn't exist)
WATCH_DIR = Path(__file__).parent.parent / "watch_inbox"
WATCH_DIR.mkdir(exist_ok=True)


@on_created(str(WATCH_DIR), pattern="*.txt")
def handle_created(event: FileEvent) -> None:
    """Called when a new .txt file is created."""
    print(f"✨ Created: {event.path.name}")
    print(f"   Content: {event.path.read_text()[:100]}...")


@on_modified(str(WATCH_DIR), pattern="*.txt")
def handle_modified(event: FileEvent) -> None:
    """Called when a .txt file is modified."""
    print(f"📝 Modified: {event.path.name}")
    print(f"   New size: {event.path.stat().st_size} bytes")


@on_deleted(str(WATCH_DIR), pattern="*.txt")
def handle_deleted(event: FileEvent) -> None:
    """Called when a .txt file is deleted."""
    print(f"🗑️  Deleted: {event.path.name}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FlowWatch Basic Example")
    print("=" * 60)
    print(f"\n📁 Watch directory: {WATCH_DIR.absolute()}")
    print("\nTry these commands in another terminal:")
    print(f'  echo "Hello" > {WATCH_DIR}/test.txt')
    print(f'  echo "World" >> {WATCH_DIR}/test.txt')
    print(f"  rm {WATCH_DIR}/test.txt")
    print("\nPress Ctrl+C to stop.\n")
    run()

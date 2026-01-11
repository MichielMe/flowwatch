"""Example showing basic FlowWatch usage with decorators."""

from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run_flowwatch

# Create a local watch directory (will be created if it doesn't exist)
WATCH_DIR = Path(__file__).parent / "watch_inbox"
WATCH_DIR.mkdir(exist_ok=True)


@on_created(str(WATCH_DIR), pattern="*.txt")
def handle_new_text(event: FileEvent) -> None:
    """Handle newly created text files."""
    print(f"[handler] New text file at {event.path} (created? {event.is_created})")
    print(event.path.read_text())


@on_deleted(str(WATCH_DIR), pattern="*.txt")
def handle_deleted_text(event: FileEvent) -> None:
    """Handle deleted text files."""
    print(f"[handler] Deleted text file at {event.path} (deleted? {event.is_deleted})")


@on_modified(str(WATCH_DIR), pattern="*.txt")
def handle_modified_text(event: FileEvent) -> None:
    """Handle modified text files."""
    print(
        f"[handler] Modified text file at {event.path} (modified? {event.is_modified})"
    )
    print(event.path.read_text())


if __name__ == "__main__":
    print(f"\n📁 Drop files into '{WATCH_DIR.absolute()}' to see events!\n")
    run_flowwatch()

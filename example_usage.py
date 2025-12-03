# myproject/watchers.py
from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run_flowwatch

WATCH_DIR = Path("../bot")


@on_created(str(WATCH_DIR), pattern="*.txt")
def handle_new_text(event: FileEvent) -> None:
    print(f"[handler] New text file at {event.path} (created? {event.is_created})")
    print(event.path.read_text())


@on_deleted(str(WATCH_DIR), pattern="*.txt")
def handle_deleted_text(event: FileEvent) -> None:
    print(f"[handler] Deleted text file at {event.path} (deleted? {event.is_deleted})")


@on_modified(str(WATCH_DIR), pattern="*.txt")
def handle_modified_text(event: FileEvent) -> None:
    print(
        f"[handler] Modified text file at {event.path} (modified? {event.is_modified})"
    )
    print(event.path.read_text())


if __name__ == "__main__":
    run_flowwatch()

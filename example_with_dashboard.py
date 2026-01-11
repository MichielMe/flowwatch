"""Example showing FlowWatch with the web dashboard."""

from pathlib import Path

from flowwatch import FileEvent, on_created, on_deleted, on_modified, run_with_dashboard

# Create local watch directories (will be created if they don't exist)
WATCH_DIR = Path(__file__).parent / "watch_inbox"
WATCH_DIR.mkdir(exist_ok=True)

WATCH_DIR_2 = Path(__file__).parent / "watch_data"
WATCH_DIR_2.mkdir(exist_ok=True)


# Handlers for WATCH_DIR_2 (watch_data)
@on_created(str(WATCH_DIR_2), pattern="*.txt")
def handle_new_text_2(event: FileEvent) -> None:
    print(f"[data] New text file: {event.path.name}")


@on_modified(str(WATCH_DIR_2), pattern="*.txt")
def handle_modified_text_2(event: FileEvent) -> None:
    print(f"[data] Modified: {event.path.name}")


@on_deleted(str(WATCH_DIR_2), pattern="*.txt")
def handle_deleted_text_2(event: FileEvent) -> None:
    print(f"[data] Deleted: {event.path.name}")


@on_created(str(WATCH_DIR_2), pattern="*.json")
def handle_new_json_2(event: FileEvent) -> None:
    print(f"[data] New JSON file: {event.path.name}")


# Handlers for WATCH_DIR (watch_inbox)
@on_created(str(WATCH_DIR), pattern="*.txt")
def handle_new_text(event: FileEvent) -> None:
    print(f"[inbox] New text file: {event.path.name}")


@on_modified(str(WATCH_DIR), pattern="*.txt")
def handle_modified_text(event: FileEvent) -> None:
    print(f"[inbox] Modified: {event.path.name}")


@on_deleted(str(WATCH_DIR), pattern="*.txt")
def handle_deleted_text(event: FileEvent) -> None:
    print(f"[inbox] Deleted: {event.path.name}")


@on_created(str(WATCH_DIR), pattern="*.json")
def handle_new_json(event: FileEvent) -> None:
    print(f"[inbox] New JSON file: {event.path.name}")


@on_created(str(WATCH_DIR), pattern="*.py")
def handle_new_python(event: FileEvent) -> None:
    print(f"[inbox] New Python file: {event.path.name}")


@on_modified(str(WATCH_DIR), pattern="*.py")
def handle_modified_python(event: FileEvent) -> None:
    print(f"[inbox] Modified Python: {event.path.name}")


@on_created(str(WATCH_DIR_2), pattern="*.py")
def handle_new_python_2(event: FileEvent) -> None:
    print(f"[data] New Python file: {event.path.name}")


@on_modified(str(WATCH_DIR_2), pattern="*.py")
def handle_modified_python_2(event: FileEvent) -> None:
    print(f"[data] Modified Python: {event.path.name}")


if __name__ == "__main__":
    print("\n📁 Drop files into these directories to see events:")
    print(f"   - {WATCH_DIR.absolute()}")
    print(f"   - {WATCH_DIR_2.absolute()}\n")
    run_with_dashboard()

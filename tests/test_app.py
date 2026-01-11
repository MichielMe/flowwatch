"""Tests for the FlowWatchApp core functionality."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Event, Thread
from typing import TYPE_CHECKING

import pytest
from watchfiles import Change

from flowwatch import FileEvent, FlowWatchApp
from flowwatch.app import JsonFormatter

if TYPE_CHECKING:
    pass


class TestFileEvent:
    """Tests for the FileEvent dataclass."""

    def test_is_created(self, temp_dir: Path) -> None:
        event = FileEvent(
            change=Change.added,
            path=temp_dir / "file.txt",
            root=temp_dir,
            pattern="*.txt",
        )
        assert event.is_created is True
        assert event.is_modified is False
        assert event.is_deleted is False

    def test_is_modified(self, temp_dir: Path) -> None:
        event = FileEvent(
            change=Change.modified,
            path=temp_dir / "file.txt",
            root=temp_dir,
            pattern="*.txt",
        )
        assert event.is_created is False
        assert event.is_modified is True
        assert event.is_deleted is False

    def test_is_deleted(self, temp_dir: Path) -> None:
        event = FileEvent(
            change=Change.deleted,
            path=temp_dir / "file.txt",
            root=temp_dir,
            pattern="*.txt",
        )
        assert event.is_created is False
        assert event.is_modified is False
        assert event.is_deleted is True

    def test_frozen(self, temp_dir: Path) -> None:
        """FileEvent should be immutable (frozen dataclass)."""
        event = FileEvent(
            change=Change.added,
            path=temp_dir / "file.txt",
            root=temp_dir,
        )
        with pytest.raises(AttributeError):
            event.change = Change.modified  # type: ignore[misc]


class TestFlowWatchAppInit:
    """Tests for FlowWatchApp initialization."""

    def test_default_values(self) -> None:
        app = FlowWatchApp()
        assert app.name == "flowwatch"
        assert app.debounce == 1.6
        assert app.recursive is True
        assert app.max_workers == 4
        assert app.handlers == ()

    def test_custom_values(self) -> None:
        app = FlowWatchApp(
            name="custom",
            debounce=0.5,
            recursive=False,
            max_workers=8,
        )
        assert app.name == "custom"
        assert app.debounce == 0.5
        assert app.recursive is False
        assert app.max_workers == 8

    def test_debounce_property_setter(self) -> None:
        """Test that debounce can be set after initialization."""
        app = FlowWatchApp(debounce=1.0)
        assert app.debounce == 1.0

        app.debounce = 2.5
        assert app.debounce == 2.5
        # Internal value should be milliseconds
        assert app._debounce_ms == 2500

    def test_debounce_conversion_to_ms(self) -> None:
        """Test that debounce in seconds converts correctly to milliseconds."""
        app = FlowWatchApp(debounce=1.5)
        assert app._debounce_ms == 1500

    def test_json_logs_creates_json_handler(self) -> None:
        """Test that json_logs=True creates a JSON formatter."""
        app = FlowWatchApp(name="test-json", json_logs=True)
        assert len(app.logger.handlers) == 1
        handler = app.logger.handlers[0]
        assert isinstance(handler.formatter, JsonFormatter)

    def test_json_logs_false_creates_rich_handler(self) -> None:
        """Test that json_logs=False (default) creates a Rich handler."""
        from rich.logging import RichHandler

        app = FlowWatchApp(name="test-rich", json_logs=False)
        assert len(app.logger.handlers) == 1
        assert isinstance(app.logger.handlers[0], RichHandler)


class TestHandlerRegistration:
    """Tests for handler registration."""

    def test_add_handler(self, watch_app: FlowWatchApp, temp_dir: Path) -> None:
        def handler(event: FileEvent) -> None:
            pass

        watch_app.add_handler(
            handler,
            root=temp_dir,
            events=[Change.added],
            pattern="*.txt",
        )

        assert len(watch_app.handlers) == 1
        h = watch_app.handlers[0]
        assert h.func is handler
        assert h.root == temp_dir.resolve()
        assert h.events == frozenset([Change.added])
        assert h.pattern == "*.txt"
        assert h.process_existing is False
        assert h.priority == 0

    def test_add_handler_with_process_existing(
        self, watch_app: FlowWatchApp, temp_dir: Path
    ) -> None:
        def handler(event: FileEvent) -> None:
            pass

        watch_app.add_handler(
            handler,
            root=temp_dir,
            events=[Change.added],
            process_existing=True,
        )

        assert watch_app.handlers[0].process_existing is True

    def test_handlers_sorted_by_priority(
        self, watch_app: FlowWatchApp, temp_dir: Path
    ) -> None:
        """Handlers should be sorted by priority (descending)."""
        handlers_called: list[int] = []

        def make_handler(priority: int):
            def handler(event: FileEvent) -> None:
                handlers_called.append(priority)
            return handler

        watch_app.add_handler(
            make_handler(1), root=temp_dir, events=[Change.added], priority=1
        )
        watch_app.add_handler(
            make_handler(3), root=temp_dir, events=[Change.added], priority=3
        )
        watch_app.add_handler(
            make_handler(2), root=temp_dir, events=[Change.added], priority=2
        )

        # Check internal order
        priorities = [h.priority for h in watch_app.handlers]
        assert priorities == [3, 2, 1]

    def test_handlers_tuple_is_readonly(
        self, watch_app: FlowWatchApp, temp_dir: Path
    ) -> None:
        """The handlers property should return a tuple (immutable)."""

        def handler(event: FileEvent) -> None:
            pass

        watch_app.add_handler(handler, root=temp_dir, events=[Change.added])
        handlers = watch_app.handlers
        assert isinstance(handlers, tuple)


class TestHandlerMatching:
    """Tests for the _Handler.matches() method."""

    def test_matches_event_type(self, temp_dir: Path) -> None:
        """Handler should only match registered event types."""
        # Resolve temp_dir to handle symlinks (e.g. /var -> /private/var on macOS)
        temp_dir = temp_dir.resolve()
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added])
        h = app._handlers[0]

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        assert h.matches(Change.added, test_file) is True
        assert h.matches(Change.modified, test_file) is False
        assert h.matches(Change.deleted, test_file) is False

    def test_matches_pattern_filename(self, temp_dir: Path) -> None:
        """Handler should match patterns against filename."""
        temp_dir = temp_dir.resolve()
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added], pattern="*.txt")
        h = app._handlers[0]

        txt_file = temp_dir / "test.txt"
        txt_file.write_text("content")

        json_file = temp_dir / "test.json"
        json_file.write_text("{}")

        assert h.matches(Change.added, txt_file) is True
        assert h.matches(Change.added, json_file) is False

    def test_matches_pattern_relative_path(self, temp_dir: Path) -> None:
        """Handler should match patterns against relative path."""
        temp_dir = temp_dir.resolve()
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(
            handler, root=temp_dir, events=[Change.added], pattern="subdir/*.txt"
        )
        h = app._handlers[0]

        subdir = temp_dir / "subdir"
        subdir.mkdir()
        nested_file = subdir / "test.txt"
        nested_file.write_text("content")

        root_file = temp_dir / "test.txt"
        root_file.write_text("content")

        assert h.matches(Change.added, nested_file) is True
        assert h.matches(Change.added, root_file) is False

    def test_matches_outside_root_returns_false(self, temp_dir: Path) -> None:
        """Handler should not match files outside its root."""
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        subdir = temp_dir / "watched"
        subdir.mkdir()
        app.add_handler(handler, root=subdir, events=[Change.added])
        h = app._handlers[0]

        outside_file = temp_dir / "outside.txt"
        outside_file.write_text("content")

        assert h.matches(Change.added, outside_file.resolve()) is False

    def test_matches_ignores_directories_for_non_delete(self, temp_dir: Path) -> None:
        """Handler should ignore directories for created/modified events."""
        temp_dir = temp_dir.resolve()
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(
            handler, root=temp_dir, events=[Change.added, Change.modified]
        )
        h = app._handlers[0]

        subdir = temp_dir / "subdir"
        subdir.mkdir()

        assert h.matches(Change.added, subdir) is False
        assert h.matches(Change.modified, subdir) is False

    def test_matches_deleted_file_no_is_dir_check(self, temp_dir: Path) -> None:
        """Deleted files should not fail on is_dir() check since file doesn't exist."""
        temp_dir = temp_dir.resolve()
        app = FlowWatchApp()

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.deleted])
        h = app._handlers[0]

        # File that doesn't exist (was deleted)
        deleted_file = temp_dir / "deleted.txt"
        # This should NOT raise or return False due to is_dir() check
        assert h.matches(Change.deleted, deleted_file) is True


class TestRunWithStopEvent:
    """Tests for the run loop with stop_event."""

    def test_run_without_handlers_raises(self, watch_app: FlowWatchApp) -> None:
        """Running without handlers should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="No handlers registered"):
            watch_app.run()

    def test_run_stops_on_stop_event(
        self, watch_app: FlowWatchApp, temp_dir: Path
    ) -> None:
        """Run should stop when stop_event is set."""

        def handler(event: FileEvent) -> None:
            pass

        watch_app.add_handler(handler, root=temp_dir, events=[Change.added])

        stop_event = Event()

        def stop_after_delay() -> None:
            time.sleep(0.2)
            stop_event.set()

        thread = Thread(target=stop_after_delay)
        thread.start()

        start = time.time()
        watch_app.run(stop_event=stop_event)
        elapsed = time.time() - start

        thread.join()
        assert elapsed < 1.0  # Should stop quickly after event is set

    def test_run_twice_raises(
        self, watch_app: FlowWatchApp, temp_dir: Path
    ) -> None:
        """Running while already running should raise RuntimeError."""

        def handler(event: FileEvent) -> None:
            pass

        watch_app.add_handler(handler, root=temp_dir, events=[Change.added])

        stop_event = Event()
        error_occurred = Event()
        error_message: list[str] = []

        def run_app() -> None:
            watch_app.run(stop_event=stop_event)

        def try_run_again() -> None:
            time.sleep(0.1)
            try:
                watch_app.run()
            except RuntimeError as e:
                error_message.append(str(e))
                error_occurred.set()
            finally:
                stop_event.set()

        t1 = Thread(target=run_app)
        t2 = Thread(target=try_run_again)

        t1.start()
        t2.start()

        t1.join(timeout=2)
        t2.join(timeout=2)

        assert error_occurred.is_set()
        assert "already running" in error_message[0]


class TestProcessExistingFiles:
    """Tests for process_existing functionality."""

    def test_process_existing_on_startup(self, temp_dir: Path) -> None:
        """Handlers with process_existing=True should process files on startup."""
        temp_dir = temp_dir.resolve()
        # Create files before starting the watcher
        file1 = temp_dir / "existing1.txt"
        file2 = temp_dir / "existing2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        processed_files: set[Path] = set()

        def handler(event: FileEvent) -> None:
            processed_files.add(event.path)

        app = FlowWatchApp(debounce=0.1)
        app.add_handler(
            handler,
            root=temp_dir,
            events=[Change.added],
            pattern="*.txt",
            process_existing=True,
        )

        stop_event = Event()

        def stop_soon() -> None:
            time.sleep(0.3)
            stop_event.set()

        thread = Thread(target=stop_soon)
        thread.start()

        app.run(stop_event=stop_event)
        thread.join()

        # Both existing files should have been processed (use set to handle duplicates)
        assert len(processed_files) == 2
        assert file1 in processed_files
        assert file2 in processed_files


class TestEventDispatching:
    """Tests for event dispatching to handlers."""

    def test_handler_receives_events(self, temp_dir: Path) -> None:
        """Handler should receive file events."""
        received_events: list[FileEvent] = []

        def handler(event: FileEvent) -> None:
            received_events.append(event)

        app = FlowWatchApp(debounce=0.1)
        app.add_handler(handler, root=temp_dir, events=[Change.added], pattern="*.txt")

        stop_event = Event()

        def create_file_and_stop() -> None:
            time.sleep(0.2)
            test_file = temp_dir / "new_file.txt"
            test_file.write_text("hello")
            time.sleep(0.3)
            stop_event.set()

        thread = Thread(target=create_file_and_stop)
        thread.start()

        app.run(stop_event=stop_event)
        thread.join()

        assert len(received_events) >= 1
        event = received_events[0]
        assert event.change == Change.added
        assert event.path.name == "new_file.txt"
        assert event.root == temp_dir.resolve()
        assert event.pattern == "*.txt"

    def test_handler_exception_is_logged_not_raised(self, temp_dir: Path) -> None:
        """Handler exceptions should be caught and logged, not crash the app."""
        call_count = [0]

        def bad_handler(event: FileEvent) -> None:
            call_count[0] += 1
            raise ValueError("Handler failed!")

        app = FlowWatchApp(debounce=0.1)
        app.add_handler(
            bad_handler,
            root=temp_dir,
            events=[Change.added],
            pattern="*.txt",
            process_existing=True,
        )

        # Create file before starting
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        stop_event = Event()

        def stop_soon() -> None:
            time.sleep(0.3)
            stop_event.set()

        thread = Thread(target=stop_soon)
        thread.start()

        # Should not raise
        app.run(stop_event=stop_event)
        thread.join()

        # Handler was called despite raising
        assert call_count[0] >= 1


class TestJsonFormatter:
    """Tests for the JsonFormatter logging class."""

    def test_format_basic_message(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_args(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Value is %s",
            args=("hello",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Value is hello"

    def test_format_with_exception(self) -> None:
        formatter = JsonFormatter()
        import sys

        def raise_error() -> None:
            raise ValueError("test error")

        try:
            raise_error()
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "test error" in data["exception"]

    def test_format_timestamp_is_iso(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        # Should be ISO format with timezone
        from datetime import datetime
        timestamp = data["timestamp"]
        # Should parse without error
        datetime.fromisoformat(timestamp)


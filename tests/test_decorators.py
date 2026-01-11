"""Tests for the decorator-based API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from watchfiles import Change

from flowwatch import (
    FileEvent,
    FlowWatchApp,
    on_any,
    on_created,
    on_deleted,
    on_modified,
)
from flowwatch.decorators import _ensure_app, default_app


class TestEnsureApp:
    """Tests for the _ensure_app helper function."""

    def test_returns_default_app_when_none(self) -> None:
        result = _ensure_app(None)
        assert result is default_app

    def test_returns_custom_app_when_provided(self) -> None:
        custom_app = FlowWatchApp(name="custom")
        result = _ensure_app(custom_app)
        assert result is custom_app


class TestOnCreatedDecorator:
    """Tests for the @on_created decorator."""

    def test_registers_handler_for_added_event(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_created(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 1
        h = app.handlers[0]
        assert h.func is handler
        assert h.events == frozenset([Change.added])
        assert h.pattern is None
        assert h.process_existing is False

    def test_registers_with_pattern(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_created(str(temp_dir), pattern="*.json", app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert app.handlers[0].pattern == "*.json"

    def test_registers_with_process_existing(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_created(str(temp_dir), process_existing=True, app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert app.handlers[0].process_existing is True

    def test_registers_with_priority(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_created(str(temp_dir), priority=10, app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert app.handlers[0].priority == 10

    def test_uses_default_app_when_not_specified(self, temp_dir: Path) -> None:
        """When no app is provided, uses the default_app."""
        # Store original handler count
        original_count = len(default_app.handlers)

        @on_created(str(temp_dir))
        def handler(event: FileEvent) -> None:
            pass

        assert len(default_app.handlers) == original_count + 1

        # Cleanup: remove the handler we just added
        default_app._handlers.pop()

    def test_returns_original_function(self, temp_dir: Path) -> None:
        """Decorator should return the original function unchanged."""
        app = FlowWatchApp(name="test")

        def original_handler(event: FileEvent) -> None:
            return None

        decorated = on_created(str(temp_dir), app=app)(original_handler)
        assert decorated is original_handler


class TestOnModifiedDecorator:
    """Tests for the @on_modified decorator."""

    def test_registers_handler_for_modified_event(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_modified(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 1
        h = app.handlers[0]
        assert h.events == frozenset([Change.modified])

    def test_process_existing_always_false(self, temp_dir: Path) -> None:
        """on_modified should always have process_existing=False (it's meaningless)."""
        app = FlowWatchApp(name="test")

        @on_modified(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        # on_modified doesn't accept process_existing parameter
        assert app.handlers[0].process_existing is False


class TestOnDeletedDecorator:
    """Tests for the @on_deleted decorator."""

    def test_registers_handler_for_deleted_event(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_deleted(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 1
        h = app.handlers[0]
        assert h.events == frozenset([Change.deleted])

    def test_process_existing_always_false(self, temp_dir: Path) -> None:
        """on_deleted should always have process_existing=False (it's meaningless)."""
        app = FlowWatchApp(name="test")

        @on_deleted(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert app.handlers[0].process_existing is False


class TestOnAnyDecorator:
    """Tests for the @on_any decorator."""

    def test_registers_handler_for_all_events(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_any(str(temp_dir), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 1
        h = app.handlers[0]
        assert h.events == frozenset([Change.added, Change.modified, Change.deleted])

    def test_registers_with_process_existing(self, temp_dir: Path) -> None:
        app = FlowWatchApp(name="test")

        @on_any(str(temp_dir), process_existing=True, app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert app.handlers[0].process_existing is True


class TestMultipleDecorators:
    """Tests for using multiple decorators on the same function."""

    def test_same_handler_multiple_roots(self, temp_dir: Path) -> None:
        """Same handler can be registered for multiple roots."""
        app = FlowWatchApp(name="test")
        root1 = temp_dir / "dir1"
        root2 = temp_dir / "dir2"
        root1.mkdir()
        root2.mkdir()

        @on_created(str(root1), app=app)
        @on_created(str(root2), app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 2
        roots = {h.root for h in app.handlers}
        assert roots == {root1.resolve(), root2.resolve()}

    def test_same_handler_multiple_patterns(self, temp_dir: Path) -> None:
        """Same handler can be registered for multiple patterns."""
        app = FlowWatchApp(name="test")

        @on_created(str(temp_dir), pattern="*.txt", app=app)
        @on_created(str(temp_dir), pattern="*.json", app=app)
        def handler(event: FileEvent) -> None:
            pass

        assert len(app.handlers) == 2
        patterns = {h.pattern for h in app.handlers}
        assert patterns == {"*.txt", "*.json"}


class TestRunFunction:
    """Tests for the run() function."""

    def test_run_calls_app_run(self, temp_dir: Path) -> None:
        """run() should call the default_app.run() method."""
        from flowwatch import decorators

        # Add a handler so it doesn't fail
        app = FlowWatchApp(name="test")

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added])

        with patch.object(app, "run") as mock_run:
            # Temporarily replace default_app
            original = decorators.default_app
            decorators.default_app = app
            try:
                decorators.run(pretty=False)
            finally:
                decorators.default_app = original

            mock_run.assert_called_once()


class TestAsyncDecorators:
    """Tests for async handler support in decorators."""

    def test_on_created_with_async_handler(self, temp_dir: Path) -> None:
        """@on_created should work with async handlers."""
        app = FlowWatchApp(name="test-async")

        @on_created(str(temp_dir), app=app)
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        assert len(app.handlers) == 1
        h = app.handlers[0]
        assert h.is_async is True
        assert h.func is async_handler

    def test_on_modified_with_async_handler(self, temp_dir: Path) -> None:
        """@on_modified should work with async handlers."""
        app = FlowWatchApp(name="test-async")

        @on_modified(str(temp_dir), app=app)
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        assert len(app.handlers) == 1
        assert app.handlers[0].is_async is True

    def test_on_deleted_with_async_handler(self, temp_dir: Path) -> None:
        """@on_deleted should work with async handlers."""
        app = FlowWatchApp(name="test-async")

        @on_deleted(str(temp_dir), app=app)
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        assert len(app.handlers) == 1
        assert app.handlers[0].is_async is True

    def test_on_any_with_async_handler(self, temp_dir: Path) -> None:
        """@on_any should work with async handlers."""
        app = FlowWatchApp(name="test-async")

        @on_any(str(temp_dir), app=app)
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        assert len(app.handlers) == 1
        assert app.handlers[0].is_async is True
        assert app.handlers[0].events == frozenset(
            [Change.added, Change.modified, Change.deleted]
        )

    def test_async_decorator_returns_original_function(self, temp_dir: Path) -> None:
        """Async decorator should return the original async function unchanged."""
        app = FlowWatchApp(name="test-async")

        async def original_async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        decorated = on_created(str(temp_dir), app=app)(original_async_handler)
        assert decorated is original_async_handler

    def test_async_decorator_with_all_options(self, temp_dir: Path) -> None:
        """Async decorator should accept all options."""
        app = FlowWatchApp(name="test-async")

        @on_created(
            str(temp_dir),
            pattern="*.json",
            process_existing=True,
            priority=10,
            app=app,
        )
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        h = app.handlers[0]
        assert h.is_async is True
        assert h.pattern == "*.json"
        assert h.process_existing is True
        assert h.priority == 10

    def test_mixed_sync_async_decorators(self, temp_dir: Path) -> None:
        """Mix of sync and async handlers should work together."""
        app = FlowWatchApp(name="test-mixed")

        @on_created(str(temp_dir), pattern="*.txt", app=app)
        def sync_handler(event: FileEvent) -> None:
            pass

        @on_created(str(temp_dir), pattern="*.json", app=app)
        async def async_handler(event: FileEvent) -> None:
            await asyncio.sleep(0)

        assert len(app.handlers) == 2

        sync_h = next(h for h in app.handlers if h.pattern == "*.txt")
        async_h = next(h for h in app.handlers if h.pattern == "*.json")

        assert sync_h.is_async is False
        assert async_h.is_async is True

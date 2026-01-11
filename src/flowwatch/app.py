# src/flowwatch/app.py
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
from collections.abc import Callable, Coroutine, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any, TypeAlias

from rich.logging import RichHandler
from watchfiles import Change, watch

# Type aliases for handler functions
SyncHandler: TypeAlias = Callable[["FileEvent"], None]
AsyncHandler: TypeAlias = Callable[["FileEvent"], Coroutine[Any, Any, None]]
Handler: TypeAlias = SyncHandler | AsyncHandler


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging in production environments.

    Outputs log records as single-line JSON objects with consistent fields,
    suitable for log aggregation systems like ELK, Datadog, or CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, object] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if any
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "file_path"):
            log_data["file_path"] = record.file_path
        if hasattr(record, "handler_name"):
            log_data["handler_name"] = record.handler_name

        return json.dumps(log_data, default=str)


@dataclass(frozen=True)
class FileEvent:
    """
    A normalized event passed to handler functions.

    Attributes
    ----------
    change:
        The underlying watchfiles.Change (added, modified, deleted).
    path:
        The full path to the file that triggered the event.
    root:
        The root folder this handler is watching.
    pattern:
        The glob pattern that matched this file (if any).
    """

    change: Change
    path: Path
    root: Path
    pattern: str | None = None

    @property
    def is_created(self) -> bool:
        return self.change == Change.added

    @property
    def is_modified(self) -> bool:
        return self.change == Change.modified

    @property
    def is_deleted(self) -> bool:
        return self.change == Change.deleted


@dataclass
class _Handler:
    """
    Internal representation of a handler registration.
    """

    func: Handler
    root: Path
    events: frozenset[Change]
    pattern: str | None
    process_existing: bool
    priority: int
    is_async: bool = False

    def matches(self, change: Change, path: Path) -> bool:
        """
        Return True if this handler should be triggered for (change, path).
        """
        if change not in self.events:
            return False

        # Path must be under root
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return False

        # Ignore directories (but not for deleted events since path no longer exists)
        if change != Change.deleted and path.is_dir():
            return False

        # Pattern match (against relative path)
        if self.pattern:
            return fnmatch.fnmatch(path.name, self.pattern) or fnmatch.fnmatch(
                str(rel), self.pattern
            )

        return True


class FlowWatchApp:
    """
    Main application object for FlowWatch.

    - Register handlers bound to roots / patterns / events.
    - Run a single watchfiles loop for all roots.
    - Supports both sync and async handler functions.
    """

    def __init__(
        self,
        *,
        name: str = "flowwatch",
        debounce: float = 1.6,
        recursive: bool = True,
        max_workers: int = 4,
        logger: logging.Logger | None = None,
        json_logs: bool = False,
    ) -> None:
        """
        Initialize a FlowWatchApp instance.

        Parameters
        ----------
        name:
            Application name (used for logging).
        debounce:
            Debounce interval in seconds. Events within this window are
            batched together. Default is 1.6 seconds.
        recursive:
            Whether to watch directories recursively.
        max_workers:
            Maximum number of worker threads for handler execution.
        logger:
            Optional custom logger. If not provided, a Rich-formatted
            logger is created (or JSON logger if json_logs=True).
        json_logs:
            If True, use JSON-formatted logging suitable for production
            environments and log aggregation systems. Ignored if a custom
            logger is provided.
        """
        self.name = name
        self._debounce_ms = int(debounce * 1000)
        self.recursive = recursive
        self.max_workers = max_workers
        self._handlers: list[_Handler] = []
        self._executor: ThreadPoolExecutor | None = None
        self._json_logs = json_logs

        # Async support: event loop running in a dedicated thread
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: Thread | None = None

        # Background run support for start()/stop()
        self._stop_event: Event | None = None
        self._run_thread: Thread | None = None

        if logger is None:
            logger = logging.getLogger(name)
            if not logger.handlers:
                if json_logs:
                    log_handler: logging.Handler = logging.StreamHandler()
                    log_handler.setFormatter(JsonFormatter())
                else:
                    log_handler = RichHandler(
                        rich_tracebacks=True,
                        markup=True,
                        show_path=False,
                    )
                    # RichHandler already formats nicely; keep formatter simple
                    formatter = logging.Formatter("%(message)s")
                    log_handler.setFormatter(formatter)
                logger.addHandler(log_handler)
            logger.setLevel(logging.INFO)

        self.logger = logger

    # ---------- public API ----------

    @property
    def debounce(self) -> float:
        """Debounce interval in seconds."""
        return self._debounce_ms / 1000

    @debounce.setter
    def debounce(self, value: float) -> None:
        """Set debounce interval in seconds."""
        self._debounce_ms = int(value * 1000)

    @property
    def handlers(self) -> tuple[_Handler, ...]:
        """
        Read-only view of registered handlers (used by the CLI to render tables).
        """
        return tuple(self._handlers)

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running in the background."""
        return self._run_thread is not None and self._run_thread.is_alive()

    def start(self) -> None:
        """
        Start watching in a background thread (non-blocking).

        Use this for integration with frameworks like FastAPI where you need
        non-blocking startup. Call stop() to shut down gracefully.

        Raises
        ------
        RuntimeError:
            If the watcher is already running or no handlers are registered.
        """
        if self.is_running:
            return  # Already running

        if not self._handlers:
            raise RuntimeError("No handlers registered for FlowWatchApp.")

        self._stop_event = Event()

        self._run_thread = Thread(
            target=self.run,
            kwargs={"stop_event": self._stop_event},
            daemon=True,
        )
        self._run_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the background watcher gracefully.

        Parameters
        ----------
        timeout:
            Maximum time to wait for the watcher thread to finish.
        """
        if self._stop_event is not None:
            self._stop_event.set()

        if self._run_thread is not None and self._run_thread.is_alive():
            self._run_thread.join(timeout=timeout)

        self._stop_event = None
        self._run_thread = None

    def add_handler(
        self,
        func: Handler,
        *,
        root: str | Path,
        events: Iterable[Change],
        pattern: str | None = None,
        process_existing: bool = False,
        priority: int = 0,
    ) -> None:
        """
        Register a handler function for one or more file events.

        Handlers can be either synchronous or asynchronous (coroutine) functions.
        Async handlers are automatically detected and executed in a dedicated
        event loop thread.
        """
        root_path = Path(root).resolve()
        is_async = asyncio.iscoroutinefunction(func)

        handler = _Handler(
            func=func,
            root=root_path,
            events=frozenset(events),
            pattern=pattern,
            process_existing=process_existing,
            priority=priority,
            is_async=is_async,
        )

        handler_type = "async" if is_async else "sync"
        self.logger.debug(
            "Registering %s handler %r for root=%s pattern=%r events=%s "
            "process_existing=%s priority=%d",
            handler_type,
            func,
            root_path,
            pattern,
            [e.name for e in handler.events],
            process_existing,
            priority,
        )

        self._handlers.append(handler)
        # Keep handlers sorted by priority (desc)
        self._handlers.sort(key=lambda h: h.priority, reverse=True)

    # ---------- async event loop management ----------

    def _has_async_handlers(self) -> bool:
        """Check if any registered handlers are async."""
        return any(h.is_async for h in self._handlers)

    def _start_async_loop(self) -> None:
        """Start a dedicated event loop thread for async handlers."""
        if self._async_loop is not None:
            return  # Already running

        def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._async_loop = asyncio.new_event_loop()
        self._async_thread = Thread(
            target=_run_loop, args=(self._async_loop,), daemon=True
        )
        self._async_thread.start()
        self.logger.debug("Started async event loop thread")

    def _stop_async_loop(self) -> None:
        """Stop the async event loop thread."""
        if self._async_loop is None:
            return

        self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        if self._async_thread is not None:
            self._async_thread.join(timeout=5.0)

        self._async_loop = None
        self._async_thread = None
        self.logger.debug("Stopped async event loop thread")

    # ---------- main run loop ----------

    def run(self, *, stop_event: Event | None = None) -> None:
        """
        Start watching and dispatching events.

        This call blocks until:
        - stop_event is set, or
        - KeyboardInterrupt (Ctrl+C)
        """
        if not self._handlers:
            raise RuntimeError("No handlers registered for FlowWatchApp.")

        if stop_event is None:
            stop_event = Event()

        if self._executor is not None:
            raise RuntimeError("FlowWatchApp.run() called while already running.")

        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # Start async loop if we have async handlers
        if self._has_async_handlers():
            self._start_async_loop()

        try:
            # Initial processing of existing files (if requested)
            self._process_existing_files()

            roots = self._collect_roots()
            roots_str = ", ".join(str(r) for r in roots)
            self.logger.info(
                "[bold green]FlowWatch[/] starting on roots: [cyan]%s[/]", roots_str
            )

            for changes in watch(
                *roots,
                debounce=self._debounce_ms,
                recursive=self.recursive,
                stop_event=stop_event,
            ):
                if not changes:
                    continue
                self._dispatch_batch(changes)

        except KeyboardInterrupt:
            self.logger.info("[yellow]FlowWatch interrupted by user.[/]")
        finally:
            self.logger.info("[dim]FlowWatch shutting down '%s'...[/]", self.name)
            if self._executor is not None:
                self._executor.shutdown(wait=True)
            self._executor = None
            self._stop_async_loop()

    # ---------- internals ----------

    def _collect_roots(self) -> Sequence[Path]:
        return sorted({h.root for h in self._handlers})

    def _process_existing_files(self) -> None:
        """
        For handlers with process_existing=True and Change.added in events,
        walk the root and submit events for existing files.
        """
        for handler in self._handlers:
            if not handler.process_existing:
                continue
            if Change.added not in handler.events:
                continue

            self.logger.info(
                "Processing existing files for root=[cyan]%s[/] pattern=[magenta]%r[/]",
                handler.root,
                handler.pattern,
            )

            for path in handler.root.rglob("*"):
                if not path.is_file():
                    continue
                if handler.pattern and not (
                    fnmatch.fnmatch(path.name, handler.pattern)
                    or fnmatch.fnmatch(
                        str(path.relative_to(handler.root)), handler.pattern
                    )
                ):
                    continue

                event = FileEvent(
                    change=Change.added,
                    path=path,
                    root=handler.root,
                    pattern=handler.pattern,
                )
                self._submit(handler, event)

    def _dispatch_batch(self, changes: set[tuple[Change, str]]) -> None:
        """
        Dispatch a batch of changes coming from watchfiles.
        """
        for change, raw_path in changes:
            path = Path(raw_path).resolve()
            for handler in self._handlers:
                if not handler.matches(change, path):
                    continue
                event = FileEvent(
                    change=change,
                    path=path,
                    root=handler.root,
                    pattern=handler.pattern,
                )
                self._submit(handler, event)

    def _submit(self, handler: _Handler, event: FileEvent) -> None:
        """
        Submit a handler call to the executor, with error handling.

        Sync handlers run in the thread pool executor.
        Async handlers run in the dedicated async event loop.
        """
        if self._executor is None:
            self.logger.error(
                "[red]Executor not initialized, dropping event[/] %r", event
            )
            return

        self.logger.debug(
            "Dispatching [blue]%s[/] for [cyan]%s[/] to [magenta]%r[/] (%s)",
            event.change.name,
            event.path,
            handler.func,
            "async" if handler.is_async else "sync",
        )

        if handler.is_async:
            self._submit_async(handler, event)
        else:
            self._submit_sync(handler, event)

    def _submit_sync(self, handler: _Handler, event: FileEvent) -> None:
        """Submit a sync handler to the thread pool."""

        def _call() -> None:
            try:
                # Cast to sync handler type for the call
                sync_func: SyncHandler = handler.func  # type: ignore[assignment]
                sync_func(event)
            except Exception:
                self.logger.exception(
                    "[red]Exception in handler[/] %r for %s",
                    handler.func,
                    event.path,
                )

        if self._executor is not None:
            self._executor.submit(_call)

    def _submit_async(self, handler: _Handler, event: FileEvent) -> None:
        """Submit an async handler to the async event loop."""
        if self._async_loop is None:
            self.logger.error(
                "[red]Async loop not running, dropping event[/] %r "
                "for async handler %r",
                event,
                handler.func,
            )
            return

        async def _async_call() -> None:
            try:
                # Cast to async handler type for the call
                async_func: AsyncHandler = handler.func  # type: ignore[assignment]
                await async_func(event)
            except Exception:
                self.logger.exception(
                    "[red]Exception in async handler[/] %r for %s",
                    handler.func,
                    event.path,
                )

        asyncio.run_coroutine_threadsafe(_async_call(), self._async_loop)

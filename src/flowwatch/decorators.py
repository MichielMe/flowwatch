# src/flowwatch/decorators.py
from __future__ import annotations

from collections.abc import Callable
from threading import Event

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from watchfiles import Change

from .app import FileEvent, FlowWatchApp

# Global default app for decorator-based API
default_app = FlowWatchApp(name="flowwatch-default")


def _ensure_app(app: FlowWatchApp | None) -> FlowWatchApp:
    return app or default_app


def on_created(
    root: str,
    *,
    pattern: str | None = None,
    process_existing: bool = False,
    priority: int = 0,
    app: FlowWatchApp | None = None,
) -> Callable[[Callable[[FileEvent], None]], Callable[[FileEvent], None]]:
    """
    Decorate a function to run when a file is created (Change.added)
    under the given root (and optional pattern).
    """

    def decorator(func: Callable[[FileEvent], None]) -> Callable[[FileEvent], None]:
        _app = _ensure_app(app)
        _app.add_handler(
            func,
            root=root,
            events=[Change.added],
            pattern=pattern,
            process_existing=process_existing,
            priority=priority,
        )
        return func

    return decorator


def on_modified(
    root: str,
    *,
    pattern: str | None = None,
    priority: int = 0,
    app: FlowWatchApp | None = None,
) -> Callable[[Callable[[FileEvent], None]], Callable[[FileEvent], None]]:
    """
    Decorate a function to run when a file is modified (Change.modified).
    """

    def decorator(func: Callable[[FileEvent], None]) -> Callable[[FileEvent], None]:
        _app = _ensure_app(app)
        _app.add_handler(
            func,
            root=root,
            events=[Change.modified],
            pattern=pattern,
            process_existing=False,
            priority=priority,
        )
        return func

    return decorator


def on_deleted(
    root: str,
    *,
    pattern: str | None = None,
    priority: int = 0,
    app: FlowWatchApp | None = None,
) -> Callable[[Callable[[FileEvent], None]], Callable[[FileEvent], None]]:
    """
    Decorate a function to run when a file is deleted (Change.deleted).
    """

    def decorator(func: Callable[[FileEvent], None]) -> Callable[[FileEvent], None]:
        _app = _ensure_app(app)
        _app.add_handler(
            func,
            root=root,
            events=[Change.deleted],
            pattern=pattern,
            process_existing=False,
            priority=priority,
        )
        return func

    return decorator


def on_any(
    root: str,
    *,
    pattern: str | None = None,
    process_existing: bool = False,
    priority: int = 0,
    app: FlowWatchApp | None = None,
) -> Callable[[Callable[[FileEvent], None]], Callable[[FileEvent], None]]:
    """
    Decorate a function to run on any change (created/modified/deleted).
    """

    def decorator(func: Callable[[FileEvent], None]) -> Callable[[FileEvent], None]:
        _app = _ensure_app(app)
        _app.add_handler(
            func,
            root=root,
            events=[Change.added, Change.modified, Change.deleted],
            pattern=pattern,
            process_existing=process_existing,
            priority=priority,
        )
        return func

    return decorator


def run(*, stop_event: Event | None = None, pretty: bool = True) -> None:
    """
    Run the default FlowWatch app (used with the decorator API).

    Parameters
    ----------
    stop_event:
        Optional threading.Event to signal a graceful shutdown.
    pretty:
        If True (default), show a Rich table of registered handlers
        and a small banner before starting the watcher.
    """
    app = _ensure_app(default_app)

    if pretty:
        console = Console()
        handlers = app.handlers

        console.rule("[bold green]FlowWatch[/bold green]")

        if not handlers:
            console.print(
                "[red]No FlowWatch handlers found.[/] "
                "Did you forget to use @on_created / @on_modified decorators?"
            )
        else:
            table = Table(
                title="Registered handlers",
                box=box.SIMPLE_HEAVY,
                show_lines=False,
                highlight=True,
            )
            table.add_column("Function", style="cyan", no_wrap=True)
            table.add_column("Root", style="magenta")
            table.add_column("Events", style="green")
            table.add_column("Pattern", style="yellow")
            table.add_column("Existing?", style="blue", justify="center")
            table.add_column("Priority", justify="right")

            roots_set = set()

            for h in handlers:
                roots_set.add(h.root)
                events_str = ", ".join(e.name for e in h.events)
                table.add_row(
                    getattr(h.func, "__name__", repr(h.func)),
                    str(h.root),
                    events_str,
                    h.pattern or "—",
                    "✓" if h.process_existing else "·",
                    str(h.priority),
                )

            console.print(table)
            console.print(
                Panel.fit(
                    f"Watching [bold]{len(roots_set)}[/] root(s). "
                    "Press [bold]Ctrl+C[/] to stop.",
                    border_style="green",
                )
            )

    app.run(stop_event=stop_event)

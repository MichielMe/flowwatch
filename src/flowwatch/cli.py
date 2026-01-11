from __future__ import annotations

import importlib
import importlib.util
import logging
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .decorators import default_app
from .decorators import run as run_default_app

console = Console()
app = typer.Typer(help="FlowWatch - file-driven workflows on top of watchfiles")


def _import_target(target: str) -> None:
    """
    Import a module by name, or load a .py file by path.
    """
    # Treat anything ending in .py or containing a path separator as a file
    if target.endswith(".py") or "/" in target or "\\" in target:
        path = Path(target).expanduser().resolve()
        if not path.is_file():
            console.print(f"[red]File not found:[/] {path}")
            raise typer.Exit(1)

        spec = importlib.util.spec_from_file_location("flowwatch_handlers", path)
        if spec is None or spec.loader is None:
            console.print(f"[red]Could not load module from file:[/] {path}")
            raise typer.Exit(1)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        importlib.import_module(target)


@app.command()
def run(
    target: str = typer.Argument(
        ...,
        help=(
            "Python module or .py file to import that registers FlowWatch handlers.\n"
            "Examples: 'example_usage' or 'examples/example_usage.py'"
        ),
    ),
    debounce: float = typer.Option(
        1.6, "--debounce", "-d", help="Debounce interval in seconds."
    ),
    max_workers: int = typer.Option(4, "--max-workers", "-w"),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Watch directories recursively."
    ),
    log_level: str = typer.Option("INFO", "--log-level", "-l"),
    json_logs: bool = typer.Option(
        False,
        "--json-logs",
        help="Use JSON-formatted logs (for production/log aggregation).",
    ),
    dashboard: bool = typer.Option(
        False, "--dashboard", "--ui", help="Open real-time web dashboard."
    ),
    dashboard_port: int = typer.Option(
        8765, "--dashboard-port", help="Port for the dashboard server."
    ),
) -> None:
    """Run FlowWatch by importing a module/file that registers handlers."""
    console.rule("[bold green]FlowWatch[/bold green]")
    console.print(f"[bold]Importing:[/] [cyan]{target}[/]")

    try:
        _import_target(target)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error importing target[/red]: {exc!r}")
        raise typer.Exit(1) from None

    app_obj = default_app
    app_obj.debounce = debounce
    app_obj.max_workers = max_workers
    app_obj.recursive = recursive

    # Configure JSON logging if requested
    if json_logs:
        from .app import JsonFormatter

        # Replace existing handlers with JSON handler
        app_obj.logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        app_obj.logger.addHandler(handler)

    level = getattr(logging, log_level.upper(), logging.INFO)
    app_obj.logger.setLevel(level)

    handlers = app_obj.handlers
    if not handlers:
        console.print(
            "[red]No FlowWatch handlers found.[/] "
            "Did you forget to use @on_created / @on_modified decorators?"
        )
        raise typer.Exit(1)

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

    if dashboard:
        try:
            from .dashboard import run_dashboard

            run_dashboard(app_obj, port=dashboard_port, open_browser=True)
            console.print(
                Panel.fit(
                    f"[bold]Dashboard:[/] [cyan]http://127.0.0.1:{dashboard_port}[/]\n"
                    f"Watching [bold]{len(roots_set)}[/] root(s). "
                    "Press [bold]Ctrl+C[/] to stop.",
                    border_style="green",
                )
            )
        except ImportError:
            console.print(
                "[yellow]Dashboard dependencies not installed.[/]\n"
                "Install with: [cyan]pip install flowwatch[dashboard][/]"
            )
            raise typer.Exit(1) from None
    else:
        console.print(
            Panel.fit(
                f"Watching [bold]{len(roots_set)}[/] root(s). "
                "Press [bold]Ctrl+C[/] to stop.",
                border_style="green",
            )
        )

    run_default_app(pretty=False)


def main() -> None:
    app()

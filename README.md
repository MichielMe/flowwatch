# FlowWatch

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-123%20passed-brightgreen.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](#)

FlowWatch is a tiny ergonomic layer on top of [`watchfiles`](https://pypi.org/project/watchfiles/)
that makes it easy to build **file-driven workflows** using simple decorators and a pretty
Rich + Typer powered CLI.

![FlowWatch Dashboard](docs/images/dashboard.png)

Instead of wiring `watchfiles.watch()` manually in every project, you declare:

- _what folder(s)_ you want to watch
- _which patterns_ you care about (e.g. `*.mxf`, `*.json`)
- _which function_ should run for a given event (created / modified / deleted)

FlowWatch takes care of:

- subscribing to all roots in a single watcher loop
- debouncing and recursive watching
- dispatching events to handlers with a small thread pool
- optional processing of existing files on startup
- nicely formatted logs and a CLI overview of registered handlers
- **real-time web dashboard** for monitoring events

---

## Installation

FlowWatch is published as a normal Python package.

```bash
# Using uv (recommended)
uv add flowwatch

# Or with pip
pip install flowwatch
```

### Optional Extras

```bash
# Standalone dashboard (Starlette + uvicorn)
uv add flowwatch --extra dashboard
pip install flowwatch[dashboard]

# FastAPI integration (mount in your FastAPI app)
uv add flowwatch --extra fastapi
pip install flowwatch[fastapi]

# All features
uv add flowwatch --extra all
pip install flowwatch[all]
```

---

## Quick Start

```python
from pathlib import Path
from flowwatch import FileEvent, on_created, run

WATCH_DIR = Path("inbox")
WATCH_DIR.mkdir(exist_ok=True)


@on_created(str(WATCH_DIR), pattern="*.txt", process_existing=True)
def handle_new_text(event: FileEvent) -> None:
    print(f"New text file: {event.path}")


if __name__ == "__main__":
    run()  # blocks until Ctrl+C
```

Drop `*.txt` files into `inbox/` and watch the handler fire.

See the [`examples/`](examples/) directory for more complete examples:
- `basic.py` - Simple sync handlers
- `async_handlers.py` - Mixed sync and async handlers
- `dashboard.py` - Standalone web dashboard
- `fastapi_integration.py` - Mount dashboard in FastAPI apps

---

## Core Concepts

### 1. FileEvent

Handlers receive a `FileEvent` object describing what happened:

| Attribute       | Description                                          |
| --------------- | ---------------------------------------------------- |
| `event.change`  | `watchfiles.Change` (`added`, `modified`, `deleted`) |
| `event.path`    | `pathlib.Path` pointing to the file                  |
| `event.root`    | The root folder you registered                       |
| `event.pattern` | The glob pattern that matched (if any)               |

Convenience properties:

- `event.is_created`
- `event.is_modified`
- `event.is_deleted`

### 2. Decorators

Register handlers using decorators from `flowwatch`:

```python
@on_created(root, pattern="*.txt", process_existing=True)
@on_modified(root, pattern="*.json")
@on_deleted(root, pattern="*.bak")
@on_any(root, pattern="*.*")  # all events
```

Behind the scenes these attach to a global `FlowWatchApp` instance, which you can run
using `flowwatch.run()` or via the CLI.

### 3. Async Handler Support

FlowWatch natively supports both **sync and async handlers**. Async handlers are 
automatically detected and executed in a dedicated event loop thread:

```python
import aiohttp
from flowwatch import FileEvent, on_created, run

WATCH_DIR = "./inbox"

# Sync handler - runs in thread pool
@on_created(WATCH_DIR, pattern="*.txt")
def handle_sync(event: FileEvent) -> None:
    print(f"Sync: {event.path}")

# Async handler - runs in async event loop
@on_created(WATCH_DIR, pattern="*.json")
async def handle_async(event: FileEvent) -> None:
    async with aiohttp.ClientSession() as session:
        await session.post("https://api.example.com/webhook", json={
            "file": str(event.path),
            "event": event.change.name,
        })

if __name__ == "__main__":
    run()
```

Async handlers are ideal for:
- HTTP/API calls (using `aiohttp`, `httpx`)
- Database operations (using `asyncpg`, `motor`)
- Any I/O-bound work that benefits from `async/await`

---

## Web Dashboard

> **Note:** The dashboard requires optional dependencies. Install with `uv add flowwatch --extra dashboard`

FlowWatch includes a real-time web dashboard for monitoring file events.

Features:

- **Live event streaming** via Server-Sent Events (SSE)
- **Event statistics** (created, modified, deleted counts)
- **Watched directories** overview
- **File preview** — click any event to view file contents with syntax highlighting
- **Health check endpoint** for container orchestration (`/health`)

Click on any event row to expand it and see the file contents with syntax highlighting:

![File preview with syntax highlighting](docs/images/detail_with_syntax_highlighting.png)

### Using the Dashboard

**From Python:**

```python
from flowwatch import run_with_dashboard

# ... define your handlers ...

if __name__ == "__main__":
    run_with_dashboard(port=8765, open_browser=True)
```

**From CLI:**

```bash
flowwatch run my_handlers.py --dashboard --dashboard-port 8765
```

### Health Check Endpoint

The dashboard exposes a health endpoint for monitoring:

```bash
curl http://localhost:8765/health
```

```json
{
  "status": "healthy",
  "uptime_seconds": 123.45,
  "handlers_count": 5,
  "roots_count": 2,
  "events_processed": 42
}
```

### FastAPI Integration

Mount the FlowWatch dashboard in your existing FastAPI application:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from flowwatch import FlowWatchApp, create_dashboard_routes, on_created

flowwatch = FlowWatchApp()

@on_created("./watch_dir", pattern="*.txt", app=flowwatch)
def handle_file(event):
    print(f"New file: {event.path}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    flowwatch.start()  # Start watching in background
    yield
    flowwatch.stop()   # Graceful shutdown

app = FastAPI(lifespan=lifespan)

# Mount dashboard at /flowwatch/
app.include_router(
    create_dashboard_routes(flowwatch),
    prefix="/flowwatch",
)
```

Run with:
```bash
uv run fastapi run your_app.py
```

Dashboard available at `http://localhost:8000/flowwatch/`

---

## CLI Usage

FlowWatch ships with a Typer + Rich powered CLI.

### Run a watchers module

```bash
flowwatch run myproject.watchers
```

Or run a Python file directly:

```bash
flowwatch run ./my_handlers.py
```

The CLI will:

1. Import your handlers module
2. Show a **Rich table** with handlers, roots, events, patterns, and priorities
3. Start the watcher loop with pretty logs

### CLI Options

```bash
flowwatch run myproject.watchers \
  --debounce 2.0 \          # Debounce interval in seconds (default: 1.6)
  --max-workers 8 \          # Thread pool size (default: 4)
  --no-recursive \           # Don't watch subdirectories
  --log-level DEBUG \        # Log level: DEBUG, INFO, WARNING, ERROR
  --json-logs \              # JSON-formatted logs for production
  --dashboard \              # Open web dashboard
  --dashboard-port 8080      # Dashboard port (default: 8765)
```

### JSON Logging

For production environments and log aggregation systems (ELK, Datadog, CloudWatch):

```bash
flowwatch run myproject.watchers --json-logs
```

Output:

```json
{
  "timestamp": "2026-01-11T10:30:45.123456+00:00",
  "level": "INFO",
  "logger": "flowwatch",
  "message": "FlowWatch starting on roots: /data/inbox"
}
```

---

## FlowWatchApp (Advanced)

For more control, instantiate your own `FlowWatchApp`:

```python
from pathlib import Path
from watchfiles import Change

from flowwatch import FileEvent, FlowWatchApp

app = FlowWatchApp(
    name="my-custom-app",
    debounce=0.7,
    max_workers=8,
    json_logs=True,  # Enable structured JSON logging
)


def handle_any(event: FileEvent) -> None:
    print(event.change, event.path)


app.add_handler(
    handle_any,
    root=Path("data"),
    events=[Change.added, Change.modified, Change.deleted],
    pattern="*.*",
    process_existing=True,
)

app.run()
```

---

## Docker Integration

A common pattern is to run FlowWatch as its own **worker container**:

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    volumes:
      - media:/media

  flowwatch:
    build: ./backend
    command: flowwatch run myproject.watchers --json-logs
    depends_on:
      - backend
    volumes:
      - media:/media
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8765/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  media:
```

---

## API Reference

### Decorators

| Decorator      | Description                     |
| -------------- | ------------------------------- |
| `@on_created`  | Triggers on new files           |
| `@on_modified` | Triggers when files are changed |
| `@on_deleted`  | Triggers when files are removed |
| `@on_any`      | Triggers on any file event      |

All decorators accept:

- `root`: Directory to watch (string or Path)
- `pattern`: Glob pattern (e.g., `"*.txt"`, `"**/*.json"`)
- `process_existing`: Process existing files on startup (default: `False`)
- `priority`: Handler priority, higher runs first (default: `0`)

### Functions

| Function                   | Description                              |
| -------------------------- | ---------------------------------------- |
| `run()`                    | Start the default FlowWatchApp           |
| `run_with_dashboard()`     | Start with standalone web dashboard      |
| `stop_dashboard()`         | Stop the standalone dashboard server     |
| `create_dashboard_routes()`| Create FastAPI router for dashboard      |

### Classes

| Class           | Description                                  |
| --------------- | -------------------------------------------- |
| `FlowWatchApp`  | Main application for custom configurations   |
| `FileEvent`     | Event object passed to handlers              |
| `JsonFormatter` | Logging formatter for structured JSON output |

#### FlowWatchApp Methods

| Method          | Description                                      |
| --------------- | ------------------------------------------------ |
| `add_handler()` | Register a handler function                      |
| `run()`         | Start watching (blocking)                        |
| `start()`       | Start watching in background thread (non-blocking) |
| `stop()`        | Stop background watcher gracefully               |
| `is_running`    | Property: check if watcher is running            |

### Type Aliases

For type-annotating your handlers:

| Alias          | Description                                       |
| -------------- | ------------------------------------------------- |
| `SyncHandler`  | `Callable[[FileEvent], None]`                     |
| `AsyncHandler` | `Callable[[FileEvent], Coroutine[Any, Any, None]]`|
| `Handler`      | `SyncHandler | AsyncHandler`                      |

---

## When to Use FlowWatch

FlowWatch is a good fit when you want:

- **Simple file pipelines** like:
  - "When a new MXF appears here, run this ingester."
  - "When a JSON config changes, reload some state."
  - "When a sidecar file is deleted, clean up something else."
- **Readable, declarative code** where intent is obvious from decorators
- **Pretty terminal UX** when running workers in Docker or bare metal
- **Real-time monitoring** via the web dashboard

It is **not** trying to be a full-blown workflow engine. Think of it as a thin,
Pythonic glue layer over `watchfiles`.

---

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/MichielMe/flowwatch.git
cd flowwatch
uv sync --all-extras

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=flowwatch --cov-report=term-missing

# Lint and type check
uv run ruff check src/
uv run mypy src/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development guidelines, code style, and pull request process.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

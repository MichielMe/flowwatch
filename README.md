# FlowWatch

FlowWatch is a tiny ergonomic layer on top of [`watchfiles`](https://pypi.org/project/watchfiles/)
that makes it easy to build **file-driven workflows** using simple decorators and a pretty
Rich + Typer powered CLI.

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

---

## Installation

FlowWatch is published as a normal Python package.

Using **uv**:

```bash
uv add flowwatch
```

Using **pip**:

```bash
pip install flowwatch
```

---

## Core concepts

### 1. FileEvent

Handlers receive a `FileEvent` object describing what happened:

- `event.change` – a `watchfiles.Change` (`added`, `modified`, `deleted`)
- `event.path` – `pathlib.Path` pointing to the file
- `event.root` – the root folder you registered
- `event.pattern` – the pattern that matched (if any)

It also has convenience properties:

- `event.is_created`
- `event.is_modified`
- `event.is_deleted`

### 2. Decorators

You register handlers using decorators from `flowwatch`:

- `@on_created(root, pattern="*.txt", process_existing=True)`
- `@on_modified(root, pattern="*.json")`
- `@on_deleted(root, pattern="*.bak")`
- `@on_any(root, pattern="*.*")`

Behind the scenes these attach to a global `FlowWatchApp` instance, which you can run
using `flowwatch.run()` or via the CLI.

---

## Basic usage (embedded in your code)

The decorator + runner pattern is the simplest:

```python
from pathlib import Path
from flowwatch import FileEvent, on_created, run

WATCH_DIR = Path("inbox")
WATCH_DIR.mkdir(exist_ok=True)


@on_created(str(WATCH_DIR), pattern="*.txt", process_existing=True)
def handle_new_text(event: FileEvent) -> None:
    print(f"New text file: {event.path}")
    print("Was it created?", event.is_created)


if __name__ == "__main__":
    run()  # blocks until Ctrl+C
```

Run it:

```bash
python my_script.py
```

Then drop `*.txt` files into `inbox/` and watch the handler fire.

---

## CLI usage (Typer + Rich)

FlowWatch also ships with a small CLI, exposed as the `flowwatch` command.

You typically:

1. Create a **watchers module** that only defines handlers.
2. Call `flowwatch run your_module.path`.

### 1. Create a watchers module

For example, `myproject/watchers.py`:

```python
from pathlib import Path

from flowwatch import FileEvent, on_created

BASE = Path("/media/incoming")

@on_created(str(BASE), pattern="*.mxf", process_existing=True)
def handle_mxf(event: FileEvent) -> None:
    print(f"[handler] New MXF at {event.path}")
```

### 2. Run via CLI

```bash
flowwatch run myproject.watchers
```

The CLI will:

- import `myproject.watchers`
- discover all handlers registered via decorators
- show a **Rich table** with handlers, roots, events, patterns, and priorities
- start the watcher loop and stream pretty logs to your terminal

You can customize:

```bash
flowwatch run myproject.watchers \
  --debounce 8 \
  --max-workers 8 \
  --no-recursive \
  --log-level DEBUG
```

---

## Using FlowWatch with Docker

A common pattern is to run FlowWatch as its own **worker container**:

```yaml
services:
  backend:
    build: ./backend
    volumes:
      - media:/media

  flowwatch:
    build: ./backend
    command: flowwatch run myproject.watchers
    depends_on:
      - backend
    volumes:
      - media:/media
    restart: unless-stopped

volumes:
  media:
```

Where `myproject/watchers.py` inside the image contains your handlers and watches
paths under `/media` (shared volume with the backend).

---

## FlowWatchApp (advanced / custom apps)

If you need more control than the global decorators/CLI, you can instantiate your
own `FlowWatchApp`:

```python
from pathlib import Path
from watchfiles import Change

from flowwatch import FileEvent, FlowWatchApp

app = FlowWatchApp(name="my-custom-app", debounce=0.7, max_workers=8)

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

This is the same engine used under the hood by the decorators and CLI.

---

## When should you use FlowWatch?

FlowWatch is a good fit when you want:

- **simple file pipelines** like:
  - "When a new MXF appears here, run this ingester."
  - "When a JSON config changes, reload some state."
  - "When a sidecar file is deleted, clean up something else."
- readable, declarative code:
  - your intent is obvious from the decorators
- a **pretty terminal UX** when running workers in Docker, k8s, or bare metal

It is **not** trying to be a full-blown workflow engine. Think of it as a thin,
Pythonic glue layer over `watchfiles`.

---

## Roadmap / ideas

Potential future additions:

- `async` mode using `watchfiles.awatch`
- optional structured JSON logs for production
- pattern-based routing helpers (e.g. per-extension multiplexing)
- more first-class Docker/Kubernetes examples

If you end up using FlowWatch in your own projects, feel free to open issues or
PRs with real-world improvements.

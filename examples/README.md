# FlowWatch Examples

This directory contains example scripts demonstrating FlowWatch features.

## Setup

```bash
# Install FlowWatch with dashboard support (standalone server)
uv add flowwatch --extra dashboard

# Or with FastAPI integration
uv add flowwatch --extra fastapi

# Or all features
uv add flowwatch --extra all
```

## Running Examples

```bash
# Basic usage with decorators
uv run examples/basic.py

# With the standalone web dashboard
uv run examples/dashboard.py

# FastAPI integration (mount dashboard in your app)
uv run examples/fastapi_integration.py

# Async handlers (sync + async mixed)
uv run examples/async_handlers.py
```

## Watch Directories

Each example automatically creates a `watch_inbox/` directory (and `watch_data/` for the dashboard example) when you run it. Drop files into these directories to trigger the handlers.

**Note:** The watch directories are gitignored and not part of the repository.

## Examples Overview

| File                    | Description                                               |
| ----------------------- | --------------------------------------------------------- |
| `basic.py`              | Simple sync handlers for created/modified/deleted events  |
| `dashboard.py`          | Standalone dashboard with multiple watch directories      |
| `fastapi_integration.py`| Mount dashboard in existing FastAPI app                   |
| `async_handlers.py`     | Mix of sync and async handlers                            |

## FastAPI Integration

Mount the FlowWatch dashboard in your existing FastAPI application:

```python
from fastapi import FastAPI
from flowwatch import FlowWatchApp, create_dashboard_routes, on_created

app = FastAPI()
flowwatch = FlowWatchApp()

# Mount at /flowwatch/
app.include_router(
    create_dashboard_routes(flowwatch),
    prefix="/flowwatch",
)

@on_created("./watch_dir", app=flowwatch)
def handle_file(event):
    print(f"New file: {event.path}")
```

## Quick Test

After starting an example, try these commands in another terminal:

```bash
# Create a file
echo "Hello FlowWatch!" > watch_inbox/test.txt

# Modify it
echo "Modified content" >> watch_inbox/test.txt

# Delete it
rm watch_inbox/test.txt
```

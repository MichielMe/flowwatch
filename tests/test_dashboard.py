"""Tests for the dashboard functionality."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from watchfiles import Change

from flowwatch import FileEvent, FlowWatchApp

if TYPE_CHECKING:
    pass


# Skip all tests if dashboard dependencies are not installed
pytest.importorskip("starlette")
pytest.importorskip("uvicorn")

from starlette.testclient import TestClient

from flowwatch.dashboard import (
    DASHBOARD_AVAILABLE,
    DashboardServer,
    DashboardState,
    EventRecord,
    _create_dashboard_app,
    _get_dashboard_html,
    _load_dashboard_html,
    _state,
    create_event_hook,
    run_dashboard,
    stop_dashboard,
)


class TestEventRecord:
    """Tests for the EventRecord dataclass."""

    def test_create_event_record(self) -> None:
        record = EventRecord(
            timestamp="12:34:56.789",
            change_type="added",
            path="/test/file.txt",
            handler="test_handler",
            pattern="*.txt",
        )
        assert record.timestamp == "12:34:56.789"
        assert record.change_type == "added"
        assert record.path == "/test/file.txt"
        assert record.handler == "test_handler"
        assert record.pattern == "*.txt"

    def test_to_dict(self) -> None:
        record = EventRecord(
            timestamp="12:34:56.789",
            change_type="modified",
            path="/test/file.json",
            handler="json_handler",
            pattern="*.json",
        )
        result = record.to_dict()
        assert result == {
            "timestamp": "12:34:56.789",
            "change_type": "modified",
            "path": "/test/file.json",
            "handler": "json_handler",
            "pattern": "*.json",
        }

    def test_to_dict_with_none_pattern(self) -> None:
        record = EventRecord(
            timestamp="12:34:56.789",
            change_type="deleted",
            path="/test/file.txt",
            handler="any_handler",
            pattern=None,
        )
        result = record.to_dict()
        assert result["pattern"] is None


class TestDashboardState:
    """Tests for the DashboardState dataclass."""

    def test_initial_state(self) -> None:
        state = DashboardState()
        assert len(state.events) == 0
        assert state.stats == {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        assert state.handlers == []
        assert state.roots == []
        assert len(state.subscribers) == 0

    def test_add_event(self) -> None:
        state = DashboardState()
        record = EventRecord(
            timestamp="12:34:56.789",
            change_type="added",
            path="/test/file.txt",
            handler="test_handler",
            pattern="*.txt",
        )
        state.add_event(record)

        assert len(state.events) == 1
        assert state.events[0] == record
        assert state.stats["added"] == 1
        assert state.stats["total"] == 1

    def test_add_event_updates_stats(self) -> None:
        state = DashboardState()

        # Add various event types
        state.add_event(
            EventRecord("1", "added", "/f1.txt", "h", None)
        )
        state.add_event(
            EventRecord("2", "modified", "/f2.txt", "h", None)
        )
        state.add_event(
            EventRecord("3", "deleted", "/f3.txt", "h", None)
        )
        state.add_event(
            EventRecord("4", "added", "/f4.txt", "h", None)
        )

        assert state.stats["added"] == 2
        assert state.stats["modified"] == 1
        assert state.stats["deleted"] == 1
        assert state.stats["total"] == 4

    def test_events_maxlen(self) -> None:
        state = DashboardState()
        # Add more than maxlen (100) events
        for i in range(110):
            state.add_event(
                EventRecord(str(i), "added", f"/file{i}.txt", "h", None)
            )

        assert len(state.events) == 100
        # Most recent should be first (appendleft)
        assert state.events[0].path == "/file109.txt"

    def test_broadcast_to_subscribers(self) -> None:
        state = DashboardState()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
        state.subscribers.add(queue)

        state.broadcast({"type": "test", "data": "hello"})

        assert not queue.empty()
        message = queue.get_nowait()
        assert "test" in message
        assert "hello" in message

    def test_broadcast_handles_full_queue(self) -> None:
        state = DashboardState()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        queue.put_nowait("blocking")  # Fill the queue
        state.subscribers.add(queue)

        # Should not raise even with full queue
        state.broadcast({"type": "test"})

    def test_reset_clears_all_state(self) -> None:
        state = DashboardState()
        state.add_event(EventRecord("1", "added", "/f1.txt", "h", None))
        state.handlers.append({"name": "test"})
        state.roots.append("/test")
        queue: asyncio.Queue[str] = asyncio.Queue()
        state.subscribers.add(queue)

        state.reset()

        assert len(state.events) == 0
        assert state.stats == {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        assert state.handlers == []
        assert state.roots == []
        assert len(state.subscribers) == 0

    def test_start_time_set(self) -> None:
        state = DashboardState()
        assert state.start_time > 0


class TestLoadDashboardHtml:
    """Tests for loading dashboard HTML."""

    def test_load_dashboard_html(self) -> None:
        html = _load_dashboard_html()
        assert "FlowWatch" in html
        assert "<!DOCTYPE html>" in html

    def test_get_dashboard_html_caches(self) -> None:
        html1 = _get_dashboard_html()
        html2 = _get_dashboard_html()
        assert html1 is html2  # Same object (cached)


class TestCreateEventHook:
    """Tests for the event hook mechanism."""

    def test_create_event_hook_captures_events(self, temp_dir: Path) -> None:
        # Reset global state
        _state.events.clear()
        _state.stats = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        _state.handlers.clear()
        _state.roots.clear()

        app = FlowWatchApp(name="test-hook")

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added], pattern="*.txt")

        create_event_hook(app)

        # Check handlers were populated
        assert len(_state.handlers) == 1
        assert _state.handlers[0]["name"] == "handler"
        assert _state.handlers[0]["pattern"] == "*.txt"

        # Check roots were populated
        assert len(_state.roots) == 1
        assert str(temp_dir.resolve()) in _state.roots[0]

    def test_create_event_hook_with_custom_state(self, temp_dir: Path) -> None:
        """Test that a custom state instance can be passed."""
        custom_state = DashboardState()

        app = FlowWatchApp(name="test-custom-state")

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added])

        returned_state = create_event_hook(app, state=custom_state)

        # Should return the custom state
        assert returned_state is custom_state
        # Custom state should be populated
        assert len(custom_state.handlers) == 1
        assert len(custom_state.roots) == 1


class TestDashboardApp:
    """Tests for the Starlette dashboard application."""

    @pytest.fixture
    def dashboard_client(self, temp_dir: Path) -> Generator[TestClient, None, None]:
        """Create a test client for the dashboard."""
        # Reset global state
        _state.events.clear()
        _state.stats = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        _state.handlers.clear()
        _state.roots.clear()
        _state.roots.append(str(temp_dir.resolve()))

        app = _create_dashboard_app()
        with TestClient(app) as client:
            yield client

    def test_homepage_returns_html(self, dashboard_client: TestClient) -> None:
        response = dashboard_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "FlowWatch" in response.text

    def test_api_state_returns_json(self, dashboard_client: TestClient) -> None:
        response = dashboard_client.get("/api/state")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert "stats" in data
        assert "events" in data
        assert "handlers" in data
        assert "roots" in data

    def test_api_state_reflects_current_state(
        self, dashboard_client: TestClient
    ) -> None:
        # Add an event to state
        _state.add_event(
            EventRecord("12:00:00", "added", "/test.txt", "handler", "*.txt")
        )

        response = dashboard_client.get("/api/state")
        data = response.json()

        assert data["stats"]["added"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["path"] == "/test.txt"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.fixture
    def health_client(self, temp_dir: Path) -> Generator[TestClient, None, None]:
        """Create a test client for health checks."""
        _state.reset()
        _state.roots.append(str(temp_dir.resolve()))

        app = _create_dashboard_app()
        with TestClient(app) as client:
            yield client

    def test_health_endpoint_returns_200(self, health_client: TestClient) -> None:
        response = health_client.get("/api/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, health_client: TestClient) -> None:
        response = health_client.get("/api/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_endpoint_contains_status(self, health_client: TestClient) -> None:
        response = health_client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_contains_uptime(self, health_client: TestClient) -> None:
        response = health_client.get("/api/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_endpoint_contains_counts(self, health_client: TestClient) -> None:
        response = health_client.get("/api/health")
        data = response.json()
        assert "handlers_count" in data
        assert "roots_count" in data
        assert "events_processed" in data

    def test_health_alias_endpoint(self, health_client: TestClient) -> None:
        """Test /health alias for k8s probes."""
        response = health_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestApiFileEndpoint:
    """Tests for the file preview API endpoint."""

    @pytest.fixture
    def client_with_root(self, temp_dir: Path) -> Generator[TestClient, None, None]:
        """Create a test client with temp_dir as watched root."""
        _state.events.clear()
        _state.stats = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        _state.handlers.clear()
        _state.roots.clear()
        _state.roots.append(str(temp_dir.resolve()))

        app = _create_dashboard_app()
        with TestClient(app) as client:
            yield client

    def test_file_no_path_returns_400(self, client_with_root: TestClient) -> None:
        response = client_with_root.get("/api/file")
        assert response.status_code == 400
        assert "No path provided" in response.json()["error"]

    def test_file_not_found_returns_404(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        nonexistent = temp_dir / "nonexistent.txt"
        response = client_with_root.get(f"/api/file?path={nonexistent}")
        assert response.status_code == 404
        assert "File not found" in response.json()["error"]

    def test_file_outside_root_returns_403(
        self, client_with_root: TestClient
    ) -> None:
        # Try to access /etc/passwd (path traversal attempt)
        response = client_with_root.get("/api/file?path=/etc/passwd")
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]

    def test_file_path_traversal_blocked(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        # Try path traversal with ../
        traversal_path = str(temp_dir / ".." / ".." / "etc" / "passwd")
        response = client_with_root.get(f"/api/file?path={traversal_path}")
        assert response.status_code in (403, 404)  # Either blocked or not found

    def test_file_returns_content(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        # Create a test file in the watched directory
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        response = client_with_root.get(f"/api/file?path={test_file}")
        assert response.status_code == 200

        data = response.json()
        assert data["content"] == "Hello, World!"
        assert data["is_binary"] is False
        assert data["truncated"] is False

    def test_file_returns_size_and_modified(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content")

        response = client_with_root.get(f"/api/file?path={test_file}")
        data = response.json()

        assert "size" in data
        assert data["size"] == len("Test content")
        assert "modified" in data

    def test_file_detects_binary(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        # Create a binary file (contains null bytes)
        binary_file = temp_dir / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03binary data")

        response = client_with_root.get(f"/api/file?path={binary_file}")
        data = response.json()

        assert data["is_binary"] is True
        assert "Binary file preview not available" in data.get("error", "")

    def test_file_directory_returns_400(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        response = client_with_root.get(f"/api/file?path={subdir}")
        assert response.status_code == 400
        assert "Not a file" in response.json()["error"]

    def test_file_in_subdirectory_allowed(
        self, client_with_root: TestClient, temp_dir: Path
    ) -> None:
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        test_file = subdir / "nested.txt"
        test_file.write_text("Nested content")

        response = client_with_root.get(f"/api/file?path={test_file}")
        assert response.status_code == 200
        assert response.json()["content"] == "Nested content"


class TestRunDashboard:
    """Tests for the run_dashboard function."""

    def test_run_dashboard_without_deps_raises(self) -> None:
        with patch("flowwatch.dashboard.DASHBOARD_AVAILABLE", False):
            # Need to reimport to get the patched version
            from flowwatch import dashboard

            original = dashboard.DASHBOARD_AVAILABLE
            dashboard.DASHBOARD_AVAILABLE = False
            try:
                app = FlowWatchApp(name="test")
                app.add_handler(lambda _: None, root=".", events=[Change.added])
                with pytest.raises(ImportError, match="Dashboard dependencies"):
                    run_dashboard(app)
            finally:
                dashboard.DASHBOARD_AVAILABLE = original

    def test_run_dashboard_starts_server(self, temp_dir: Path) -> None:
        """Test that run_dashboard starts the uvicorn server."""
        import uvicorn

        app = FlowWatchApp(name="test")

        def handler(event: FileEvent) -> None:
            pass

        app.add_handler(handler, root=temp_dir, events=[Change.added])

        # Mock uvicorn module to prevent actual server startup
        mock_server = MagicMock()

        with (
            patch.object(uvicorn, "Config") as mock_config_cls,
            patch.object(uvicorn, "Server", return_value=mock_server) as mock_srv,
            patch("webbrowser.open"),
        ):
            run_dashboard(app, open_browser=False)

            # Give the thread time to start
            import time
            time.sleep(0.1)

            # Config and Server should have been created
            mock_config_cls.assert_called_once()
            mock_srv.assert_called_once()
            # Server.run should have been called (in background thread)
            mock_server.run.assert_called_once()


class TestDashboardAvailability:
    """Tests for dashboard availability checks."""

    def test_dashboard_available_flag(self) -> None:
        assert DASHBOARD_AVAILABLE is True  # Since we imported starlette

    def test_create_dashboard_app_requires_deps(self) -> None:
        with patch("flowwatch.dashboard.DASHBOARD_AVAILABLE", False):
            from flowwatch import dashboard

            original = dashboard.DASHBOARD_AVAILABLE
            dashboard.DASHBOARD_AVAILABLE = False
            try:
                with pytest.raises(ImportError, match="Dashboard dependencies"):
                    _create_dashboard_app()
            finally:
                dashboard.DASHBOARD_AVAILABLE = original


class TestDashboardServer:
    """Tests for the DashboardServer class."""

    def test_dashboard_server_initial_state(self) -> None:
        server = DashboardServer()
        assert server.host == "127.0.0.1"
        assert server.port == 8765
        assert server.is_running is False

    def test_dashboard_server_url(self) -> None:
        server = DashboardServer(host="localhost", port=9000)
        assert server.url == "http://localhost:9000"

    def test_dashboard_server_state_property(self) -> None:
        server = DashboardServer()
        assert isinstance(server.state, DashboardState)

    def test_dashboard_server_start_stop(self, temp_dir: Path) -> None:
        """Test starting and stopping the server."""
        import uvicorn

        app = FlowWatchApp(name="test-server")
        app.add_handler(lambda _: None, root=temp_dir, events=[Change.added])

        server = DashboardServer()
        mock_uvicorn_server = MagicMock()

        with (
            patch.object(uvicorn, "Config"),
            patch.object(uvicorn, "Server", return_value=mock_uvicorn_server),
            patch("webbrowser.open"),
        ):
            server.start(app, open_browser=False)

            import time
            time.sleep(0.1)

            # Server should be "running" (thread started)
            mock_uvicorn_server.run.assert_called_once()

            # Stop the server
            server.stop(timeout=1.0)
            assert mock_uvicorn_server.should_exit is True

    def test_dashboard_server_double_start_noop(self, temp_dir: Path) -> None:
        """Starting an already running server should be a no-op."""
        import uvicorn

        app = FlowWatchApp(name="test-double-start")
        app.add_handler(lambda _: None, root=temp_dir, events=[Change.added])

        server = DashboardServer()
        mock_uvicorn_server = MagicMock()
        # Make a fake thread that appears to be running
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True

        with (
            patch.object(uvicorn, "Config"),
            patch.object(uvicorn, "Server", return_value=mock_uvicorn_server),
            patch("webbrowser.open"),
        ):
            server.start(app, open_browser=False)

            import time
            time.sleep(0.1)

            # Simulate that the thread is running
            server._thread = fake_thread

            # Start again should not create a new server (is_running returns True)
            server.start(app, open_browser=False)

            # Should only be called once since second start was skipped
            mock_uvicorn_server.run.assert_called_once()

            server.stop()


class TestStopDashboard:
    """Tests for the stop_dashboard function."""

    def test_stop_dashboard_when_not_running(self) -> None:
        """Stopping when no dashboard is running should not raise."""
        stop_dashboard()  # Should not raise

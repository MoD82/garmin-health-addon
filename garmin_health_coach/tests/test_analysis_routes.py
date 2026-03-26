# tests/test_analysis_routes.py
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.config import Config


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"):

        from src.main import app

        app.state.config = Config()
        app.state.analysis_running = False
        app.state.analysis_log = []
        app.state.analysis_queue = None

        with TestClient(app) as c:
            yield c


def test_trigger_analysis_redirects(client):
    with patch("src.analysis.run_analysis.run_analysis", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = None
        response = client.post("/analysis/trigger", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_trigger_while_running_redirects(client):
    client.app.state.analysis_running = True
    response = client.post("/analysis/trigger", follow_redirects=False)
    assert response.status_code in (302, 303)
    client.app.state.analysis_running = False


def test_analysis_stream_returns_event_stream(client):
    q = asyncio.Queue()
    client.app.state.analysis_queue = q
    client.app.state.analysis_log = ["🚀 Analyse gestartet"]
    q.put_nowait(None)  # immediate done

    with client.stream("GET", "/analysis/stream") as r:
        assert r.headers["content-type"].startswith("text/event-stream")


def test_manual_page_has_analysis_section(client):
    response = client.get("/manual")
    assert "Analyse" in response.text


def test_manual_page_has_trigger_button(client):
    response = client.get("/manual")
    assert "/analysis/trigger" in response.text

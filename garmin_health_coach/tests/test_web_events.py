import pytest
import asyncio
from unittest.mock import patch
from fastapi.testclient import TestClient


async def _setup(db_path):
    from src.storage.database import init_db
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    asyncio.run(_setup(db_path))
    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"):
        from src.main import app
        with TestClient(app) as c:
            yield c


def test_events_list_page_ok(client):
    """GET /events gibt 200 zurück."""
    response = client.get("/events")
    assert response.status_code == 200
    assert "Events" in response.text


def test_events_new_form_ok(client):
    """GET /events/new gibt 200 zurück."""
    response = client.get("/events/new")
    assert response.status_code == 200
    assert "event_type" in response.text


def test_events_create_and_list(client):
    """POST /events/new → Event erscheint in Liste."""
    response = client.post("/events/new", data={
        "event_type": "race",
        "date_start": "2026-06-15",
        "title": "Testrennen",
        "priority": "A",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "Testrennen" in response.text


def test_events_delete(client):
    """POST /events/{id}/delete → Event weg."""
    client.post("/events/new", data={
        "event_type": "note",
        "date_start": "2026-03-26",
        "title": "ZuLöschen",
    })
    resp = client.post("/events/1/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert "ZuLöschen" not in resp.text


def test_calendar_page_ok(client):
    """GET /calendar gibt 200 zurück."""
    response = client.get("/calendar")
    assert response.status_code == 200
    assert "Kalender" in response.text


def test_calendar_with_month_param(client):
    """GET /calendar?year=2026&month=6 gibt 200 zurück."""
    response = client.get("/calendar?year=2026&month=6")
    assert response.status_code == 200
    assert "2026" in response.text

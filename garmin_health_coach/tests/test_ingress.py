import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"):
        from src.main import app
        with TestClient(app) as c:
            yield c


def test_ingress_middleware_sets_root_path(client):
    """Mit X-Ingress-Path-Header → <base>-Tag enthält den Pfad."""
    resp = client.get(
        "/",
        headers={"X-Ingress-Path": "/api/hassio_ingress/TOKEN123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert 'href="/api/hassio_ingress/TOKEN123/"' in resp.text


def test_no_ingress_header_uses_empty_base(client):
    """Ohne Header → <base href="/">."""
    resp = client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    assert '<base href="/">' in resp.text


def test_redirect_includes_ingress_path(client):
    """POST /settings mit Ingress-Header → Redirect enthält Ingress-Pfad."""
    resp = client.post(
        "/settings",
        data={},
        headers={"X-Ingress-Path": "/api/hassio_ingress/TOKEN123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/api/hassio_ingress/TOKEN123")


def test_redirect_without_ingress_uses_absolute_path(client):
    """POST /settings ohne Header → Redirect ist normaler absoluter Pfad."""
    resp = client.post(
        "/settings",
        data={},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/settings?saved=1"

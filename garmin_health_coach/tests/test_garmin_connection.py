"""Tests für Garmin-Verbindungsstatus-Endpoints."""
import pytest
import aiosqlite
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.config import Config


@pytest.fixture
def client_no_config(tmp_path):
    """TestClient ohne Garmin-Credentials."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    cfg = Config(garmin_user="", garmin_password="")

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_with_config(tmp_path):
    """TestClient mit Garmin-Credentials, kein Token."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_with_token(tmp_path):
    """TestClient mit Credentials und vorhandenem Token."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    token_path.write_text('{"access_token": "test"}')  # Token existiert
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            c._token_path = token_path
            c._db_path = db_path
            yield c


# ── Status-Endpoint Tests ──────────────────────────────────────────────────

def test_status_no_credentials(client_no_config):
    """Keine Credentials → state='no_credentials'."""
    resp = client_no_config.get("/garmin/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "no_credentials"


def test_status_disconnected_no_token(client_with_config):
    """Credentials gesetzt, kein Token → state='disconnected'."""
    resp = client_with_config.get("/garmin/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "disconnected"


def test_status_token_only(client_with_token):
    """Token vorhanden, kein Sync → state='token_only'."""
    resp = client_with_token.get("/garmin/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "token_only"


def test_status_connected_after_success(tmp_path):
    """Token + letzter Sync erfolgreich → state='connected'."""
    import asyncio
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    token_path.write_text('{"access_token": "test"}')
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    # Erfolgreichem Sync-Eintrag in DB anlegen
    async def insert():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS analyses "
                "(date TEXT PRIMARY KEY, readiness_score INTEGER, gpt_response TEXT, "
                "weekly_plan TEXT, email_sent INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', "
                "error_message TEXT, created_at TEXT DEFAULT (datetime('now')))"
            )
            await db.execute(
                "INSERT INTO analyses (date, status) VALUES (?, ?)",
                ("2026-03-27", "success"),
            )
            await db.commit()

    asyncio.run(insert())

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            resp = c.get("/garmin/status")

    assert resp.status_code == 200
    assert resp.json()["state"] == "connected"


def test_status_rate_limited(tmp_path):
    """Letzter Sync mit 429 → state='rate_limited'."""
    import asyncio
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    token_path.write_text('{"access_token": "test"}')
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    async def insert():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS analyses "
                "(date TEXT PRIMARY KEY, readiness_score INTEGER, gpt_response TEXT, "
                "weekly_plan TEXT, email_sent INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', "
                "error_message TEXT, created_at TEXT DEFAULT (datetime('now')))"
            )
            await db.execute(
                "INSERT INTO analyses (date, status, error_message) VALUES (?, ?, ?)",
                ("2026-03-27", "error", "429 Too Many Requests"),
            )
            await db.commit()

    asyncio.run(insert())

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            resp = c.get("/garmin/status")

    assert resp.status_code == 200
    assert resp.json()["state"] == "rate_limited"


def test_status_rate_limited_ohne_token(tmp_path):
    """429-Fehler ohne Token → state='rate_limited' (Priorität vor disconnected)."""
    import asyncio
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    # Kein Token erstellt
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    async def insert():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS analyses "
                "(date TEXT PRIMARY KEY, readiness_score INTEGER, gpt_response TEXT, "
                "weekly_plan TEXT, email_sent INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', "
                "error_message TEXT, created_at TEXT DEFAULT (datetime('now')))"
            )
            await db.execute(
                "INSERT INTO analyses (date, status, error_message) VALUES (?, ?, ?)",
                ("2026-03-27", "error", "429 Too Many Requests"),
            )
            await db.commit()

    asyncio.run(insert())

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            resp = c.get("/garmin/status")

    assert resp.json()["state"] == "rate_limited"


def test_status_token_only_bei_fehler_sync(tmp_path):
    """Token + letzter Sync mit Fehler (nicht 429) → state='token_only'."""
    import asyncio
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"
    token_path.write_text('{"access_token": "test"}')
    cfg = Config(garmin_user="user@test.de", garmin_password="secret")

    async def insert():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS analyses "
                "(date TEXT PRIMARY KEY, readiness_score INTEGER, gpt_response TEXT, "
                "weekly_plan TEXT, email_sent INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', "
                "error_message TEXT, created_at TEXT DEFAULT (datetime('now')))"
            )
            await db.execute(
                "INSERT INTO analyses (date, status, error_message) VALUES (?, ?, ?)",
                ("2026-03-27", "error", "Garmin Login Fehler: Verbindung unterbrochen"),
            )
            await db.commit()

    asyncio.run(insert())

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.main.load_config", return_value=cfg):

        from src.main import app

        with TestClient(app) as c:
            resp = c.get("/garmin/status")

    assert resp.json()["state"] == "token_only"


def test_status_json_hat_alle_felder(client_no_config):
    """Response hat die Felder state, label, detail, color."""
    resp = client_no_config.get("/garmin/status")
    data = resp.json()
    assert "state" in data
    assert "label" in data
    assert "detail" in data
    assert "color" in data


# ── SSE Connect-Stream Tests ───────────────────────────────────────────────

def test_connect_stream_keine_credentials(client_no_config):
    """Keine Credentials → SSE enthält Fehlermeldung."""
    with client_no_config.stream("GET", "/garmin/connect-stream") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        content = r.read().decode()
    assert "Keine Garmin-Zugangsdaten" in content
    assert "[DONE]" in content


def test_connect_stream_erfolg(tmp_path):
    """Erfolgreicher Login → SSE enthält 'Erfolgreich'."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.collector.garmin_client.Garmin") as MockGarmin:

        mock_instance = MockGarmin.return_value
        mock_instance.login.return_value = None
        mock_instance.garth.oauth2_token = {"access_token": "tok"}

        from src.main import app
        from src.config import Config
        cfg = Config(garmin_user="user@test.de", garmin_password="secret")

        with patch("src.main.load_config", return_value=cfg):
            with TestClient(app) as c:
                with c.stream("GET", "/garmin/connect-stream") as r:
                    content = r.read().decode()

    assert "Erfolgreich" in content
    assert "[DONE]" in content


def test_connect_stream_ungueltige_credentials(tmp_path):
    """Falsches Passwort → SSE enthält 'Falscher Benutzername'."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.collector.garmin_client.Garmin") as MockGarmin:

        mock_instance = MockGarmin.return_value
        mock_instance.login.side_effect = Exception("401 Unauthorized")

        from src.main import app
        from src.config import Config
        cfg = Config(garmin_user="user@test.de", garmin_password="falsch")

        with patch("src.main.load_config", return_value=cfg):
            with TestClient(app) as c:
                with c.stream("GET", "/garmin/connect-stream") as r:
                    content = r.read().decode()

    assert "Falscher Benutzername" in content
    assert "[DONE]" in content


def test_connect_stream_sendet_fortschrittsmeldungen(tmp_path):
    """SSE-Stream sendet Schritt-für-Schritt-Meldungen."""
    db_path = tmp_path / "test.db"
    token_path = tmp_path / "garmin_token.json"

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.collector.garmin_client.DEFAULT_TOKEN_PATH", token_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"), \
         patch("src.collector.garmin_client.Garmin") as MockGarmin:

        mock_instance = MockGarmin.return_value
        mock_instance.login.return_value = None
        mock_instance.garth.oauth2_token = {"access_token": "tok"}

        from src.main import app
        from src.config import Config
        cfg = Config(garmin_user="user@test.de", garmin_password="secret")

        with patch("src.main.load_config", return_value=cfg):
            with TestClient(app) as c:
                with c.stream("GET", "/garmin/connect-stream") as r:
                    content = r.read().decode()

    assert "Prüfe Zugangsdaten" in content
    assert "Verbinde mit Garmin" in content
    assert "Login läuft" in content


# ── Template Tests ─────────────────────────────────────────────────────────

def test_settings_hat_garmin_status_banner(client_with_config):
    """Settings-Seite enthält den Garmin-Status-Banner."""
    resp = client_with_config.get("/settings")
    assert resp.status_code == 200
    assert "garmin-status" in resp.text


def test_settings_hat_verbindung_testen_button(client_with_config):
    """Settings-Seite enthält den 'Verbindung testen'-Button."""
    resp = client_with_config.get("/settings")
    assert "connect-btn" in resp.text
    assert "Verbindung testen" in resp.text


def test_settings_hat_relative_js_urls(client_with_config):
    """JS-URLs im Template sind relativ (kein führendes /)."""
    resp = client_with_config.get("/settings")
    # Relative Pfade vorhanden
    assert "garmin/status" in resp.text
    assert "garmin/connect-stream" in resp.text
    # Keine absoluten Pfade für diese Endpunkte
    assert "fetch('/garmin" not in resp.text
    assert "EventSource('/garmin" not in resp.text

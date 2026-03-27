import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.config import Config


@pytest.fixture
def client(tmp_path):
    """Erstellt einen TestClient mit gemocktem Scheduler."""
    db_path = tmp_path / "test.db"

    # Importiere app NACH den Patches
    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.scheduler.start_scheduler") as mock_start, \
         patch("src.scheduler.stop_scheduler") as mock_stop:

        from src.main import app

        # Config setzen
        app.state.config = Config()

        # TestClient mit Context Manager
        with TestClient(app) as c:
            yield c


def test_settings_page_returns_200(client):
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Einstellungen" in response.text


def test_settings_page_shows_all_sections(client):
    response = client.get("/settings")
    assert "GPT" in response.text
    assert "Analyse" in response.text
    assert "Ausgabe" in response.text
    assert "Alerts" in response.text
    assert "Sammlung" in response.text


def test_settings_post_saves_value(client):
    response = client.post(
        "/settings",
        data={"gpt_context_days": "30", "gpt_max_tokens": "2000",
              "gpt_temperature": "0.3", "gpt_include_activities": "true",
              "gpt_include_blood_pressure": "true", "gpt_include_body_composition": "true",
              "analysis_mode": "manual", "analysis_time": "08:00",
              "weekly_report_enabled": "false", "weekly_report_day": "monday",
              "output_email": "true", "output_push": "true", "output_ha_sensor": "true",
              "alert_body_battery_threshold": "30", "alert_declining_battery_days": "5",
              "alert_new_pr": "true", "alert_race_countdown_days": "7",
              "collection_mode": "auto", "collection_time": "07:30"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_settings_nav_tab_present(client):
    response = client.get("/")
    assert "Einstellungen" in response.text
    assert 'href="settings"' in response.text

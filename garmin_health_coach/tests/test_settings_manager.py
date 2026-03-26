import pytest
from unittest.mock import patch
from src.storage.database import init_db
from src.settings.manager import SettingsManager, DEFAULTS


@pytest.fixture
async def settings_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        yield db_path


async def test_get_returns_default(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        assert await mgr.get("gpt_context_days") == "14"


async def test_get_unknown_key_returns_empty(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        assert await mgr.get("nonexistent_key") == ""


async def test_set_and_get(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        await mgr.set("gpt_context_days", "30")
        assert await mgr.get("gpt_context_days") == "30"


async def test_set_overrides_default(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        await mgr.set("analysis_mode", "scheduled")
        assert await mgr.get("analysis_mode") == "scheduled"


async def test_get_all_returns_all_defaults(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        all_settings = await mgr.get_all()
        for key in DEFAULTS:
            assert key in all_settings


async def test_get_all_merges_db_values(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        await mgr.set("gpt_max_tokens", "2000")
        all_settings = await mgr.get_all()
        assert all_settings["gpt_max_tokens"] == "2000"
        assert all_settings["gpt_context_days"] == "14"  # default intact


async def test_get_int(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        assert await mgr.get_int("gpt_context_days") == 14


async def test_get_bool_true(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        assert await mgr.get_bool("gpt_include_activities") is True


async def test_get_bool_false_after_set(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        await mgr.set("output_email", "false")
        assert await mgr.get_bool("output_email") is False


async def test_get_float(settings_db):
    with patch("src.storage.database.DB_PATH", settings_db):
        mgr = SettingsManager()
        assert await mgr.get_float("gpt_temperature") == 0.4


async def test_defaults_are_complete():
    required = {
        "gpt_context_days", "gpt_include_activities", "gpt_include_blood_pressure",
        "gpt_include_body_composition", "gpt_max_tokens", "gpt_temperature",
        "analysis_mode", "analysis_time", "weekly_report_enabled", "weekly_report_day",
        "output_email", "output_push", "output_ha_sensor",
        "alert_body_battery_threshold", "alert_declining_battery_days",
        "alert_new_pr", "alert_race_countdown_days",
        "collection_mode", "collection_time",
    }
    assert required.issubset(set(DEFAULTS.keys()))

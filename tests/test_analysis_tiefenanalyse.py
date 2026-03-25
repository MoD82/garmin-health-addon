import pytest
from datetime import date, timedelta
from unittest.mock import patch
from src.storage.database import init_db
from src.analysis.tiefenanalyse import build_context_blocks


@pytest.fixture
async def populated_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        import aiosqlite
        await init_db()
        async with aiosqlite.connect(db_path) as db:
            today = date.today().isoformat()
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            await db.execute(
                "INSERT INTO daily_data (date, sleep_score, body_battery, hrv_status, stress_total) VALUES (?, 80, 70, 'balanced', 620)",
                (today,)
            )
            await db.execute(
                "INSERT INTO daily_data (date, sleep_score, body_battery) VALUES (?, 75, 65)",
                (yesterday,)
            )
            await db.execute(
                "INSERT INTO activities (date, activity_type, distance_km, norm_power) VALUES (?, 'cycling', 87.0, 234)",
                (today,)
            )
            await db.execute(
                "INSERT INTO blood_pressure (measured_at, systolic, diastolic, pulse) VALUES (?, 118, 76, 64)",
                (today + "T08:00:00",)
            )
            await db.execute(
                "INSERT INTO events (event_type, date_start, title) VALUES ('race', ?, 'Jedermann')",
                ((date.today() + timedelta(days=30)).isoformat(),)
            )
            await db.commit()
        yield db_path


async def test_returns_all_block_keys(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert set(blocks.keys()) == {"daily", "activities", "blood_pressure", "events", "checkin", "personal_records"}


async def test_daily_block_contains_data(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert len(blocks["daily"]) == 2


async def test_activities_in_blocks(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert len(blocks["activities"]) == 1
    assert blocks["activities"][0]["activity_type"] == "cycling"


async def test_exclude_activities(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14, include_activities=False)
    assert blocks["activities"] == []


async def test_blood_pressure_in_blocks(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert len(blocks["blood_pressure"]) == 1
    assert blocks["blood_pressure"][0]["systolic"] == 118


async def test_exclude_blood_pressure(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14, include_blood_pressure=False)
    assert blocks["blood_pressure"] == []


async def test_events_in_blocks(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert len(blocks["events"]) == 1
    assert blocks["events"][0]["title"] == "Jedermann"


async def test_checkin_is_none_when_empty(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=14)
    assert blocks["checkin"] is None


async def test_days_filter_limits_daily_data(populated_db):
    with patch("src.storage.database.DB_PATH", populated_db):
        blocks = await build_context_blocks(days=1)
    # Only today's record (yesterday filtered out by 1-day window)
    assert len(blocks["daily"]) == 1

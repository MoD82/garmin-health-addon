import aiosqlite
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    """Alle Tabellen werden angelegt."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_db = Path(f.name)
    with patch("src.storage.database.DB_PATH", tmp_db):
        from src.storage.database import init_db
        await init_db()
    async with aiosqlite.connect(tmp_db) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in await cursor.fetchall()
                  if not row[0].startswith("sqlite_")}
    expected = {
        "activities", "analyses", "blood_pressure",
        "daily_checkins", "daily_data", "events", "personal_records", "settings"
    }
    assert expected == tables


@pytest.mark.asyncio
async def test_wal_mode_enabled():
    """WAL-Mode ist aktiviert."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_db = Path(f.name)
    with patch("src.storage.database.DB_PATH", tmp_db):
        from src.storage.database import init_db
        await init_db()
    async with aiosqlite.connect(tmp_db) as db:
        cursor = await db.execute("PRAGMA journal_mode")
        mode = (await cursor.fetchone())[0]
    assert mode == "wal"


@pytest.mark.asyncio
async def test_init_db_idempotent():
    """Zweimaliges Aufrufen wirft keinen Fehler (IF NOT EXISTS)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_db = Path(f.name)
    with patch("src.storage.database.DB_PATH", tmp_db):
        from src.storage.database import init_db
        await init_db()
        await init_db()  # darf nicht crashen

import aiosqlite
from pathlib import Path
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)
DB_PATH = Path("/data/coach.db")

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS daily_data (
    date TEXT PRIMARY KEY,
    body_battery INTEGER,
    body_battery_charged INTEGER,
    body_battery_drained INTEGER,
    sleep_score INTEGER,
    hrv_status TEXT,
    stress_total INTEGER,
    stress_high INTEGER,
    vo2max REAL,
    weight REAL,
    body_fat REAL,
    muscle_mass REAL,
    spo2 INTEGER,
    spo2_lowest INTEGER,
    respiration REAL,
    readiness_score INTEGER
);
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT,
    activity_type TEXT DEFAULT 'unknown',
    distance_km REAL,
    duration_min INTEGER,
    elevation_m INTEGER,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_power INTEGER,
    max_power INTEGER,
    norm_power INTEGER,
    max_20min_power INTEGER,
    tss REAL,
    intensity_factor REAL,
    aero_te REAL,
    anaero_te REAL,
    training_load INTEGER
);
CREATE TABLE IF NOT EXISTS blood_pressure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measured_at TEXT NOT NULL,
    systolic INTEGER NOT NULL,
    diastolic INTEGER NOT NULL,
    pulse INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    date_start TEXT NOT NULL,
    date_end TEXT,
    title TEXT NOT NULL,
    priority TEXT,
    distance_km REAL,
    elevation_m INTEGER,
    goal TEXT,
    training_possible INTEGER DEFAULT 1,
    status TEXT DEFAULT 'planned'
);
CREATE TABLE IF NOT EXISTS daily_checkins (
    date TEXT PRIMARY KEY,
    feeling INTEGER NOT NULL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    date TEXT PRIMARY KEY,
    readiness_score INTEGER,
    gpt_response TEXT,
    weekly_plan TEXT,
    email_sent INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS personal_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_type TEXT NOT NULL,
    category TEXT NOT NULL,
    value REAL NOT NULL,
    date TEXT NOT NULL,
    UNIQUE(activity_type, category)
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(_CREATE_TABLES)
        await db.commit()
    logger.info("Datenbank initialisiert: %s", DB_PATH)


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db

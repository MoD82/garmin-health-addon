import pytest
from datetime import date
from unittest.mock import patch


@pytest.fixture
async def event_db(tmp_path):
    from src.storage.database import init_db
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        yield db_path


@pytest.mark.asyncio
async def test_create_and_get_event(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        event_id = await repo.create({
            "event_type": "race",
            "date_start": "2026-06-15",
            "title": "Jedermann 2026",
            "priority": "A",
        })
        event = await repo.get(event_id)
    assert event is not None
    assert event["title"] == "Jedermann 2026"
    assert event["event_type"] == "race"


@pytest.mark.asyncio
async def test_list_events(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        await repo.create({"event_type": "race", "date_start": "2026-06-15", "title": "Rennen A"})
        await repo.create({"event_type": "vacation", "date_start": "2026-07-01", "title": "Urlaub"})
        events = await repo.list_all()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_update_event(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        eid = await repo.create({"event_type": "race", "date_start": "2026-06-15", "title": "Alt"})
        await repo.update(eid, {"title": "Neu", "priority": "B"})
        event = await repo.get(eid)
    assert event["title"] == "Neu"
    assert event["priority"] == "B"


@pytest.mark.asyncio
async def test_delete_event(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        eid = await repo.create({"event_type": "note", "date_start": "2026-03-26", "title": "Test"})
        await repo.delete(eid)
        event = await repo.get(eid)
    assert event is None


@pytest.mark.asyncio
async def test_list_events_sorted_by_date(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        await repo.create({"event_type": "race", "date_start": "2026-09-01", "title": "Spät"})
        await repo.create({"event_type": "race", "date_start": "2026-04-01", "title": "Früh"})
        events = await repo.list_all()
    assert events[0]["title"] == "Früh"


@pytest.mark.asyncio
async def test_list_for_month(event_db):
    from src.storage.events_repo import EventsRepo
    with patch("src.storage.database.DB_PATH", event_db):
        repo = EventsRepo()
        await repo.create({"event_type": "race", "date_start": "2026-06-15", "title": "Juni-Rennen"})
        await repo.create({"event_type": "race", "date_start": "2026-07-01", "title": "Juli-Rennen"})
        await repo.create({"event_type": "note", "date_start": "2026-06-20", "title": "Juni-Notiz"})
        june = await repo.list_for_month(2026, 6)
        july = await repo.list_for_month(2026, 7)
    assert len(june) == 2
    assert all(e["date_start"].startswith("2026-06") for e in june)
    assert len(july) == 1

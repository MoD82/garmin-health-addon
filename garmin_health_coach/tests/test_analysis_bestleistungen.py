import pytest
from unittest.mock import patch
from src.storage.database import init_db
from src.storage.models import Activity
from src.analysis.bestleistungen import check_and_update_records


@pytest.fixture
async def pr_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        yield db_path


def make_activity(activity_type="cycling", distance_km=87.0, norm_power=234, max_20min_power=260) -> Activity:
    return Activity(
        date="2026-03-25",
        name="Test Activity",
        activity_type=activity_type,
        distance_km=distance_km,
        norm_power=norm_power,
        max_20min_power=max_20min_power,
    )


async def test_first_activity_creates_pr(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        act = make_activity()
        new_prs = await check_and_update_records([act])
    assert len(new_prs) > 0


async def test_same_value_no_new_pr(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        act = make_activity()
        await check_and_update_records([act])
        new_prs = await check_and_update_records([act])
    assert len(new_prs) == 0


async def test_higher_value_creates_new_pr(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        await check_and_update_records([make_activity(distance_km=87.0)])
        new_prs = await check_and_update_records([make_activity(distance_km=100.0)])
    assert any(pr["category"] == "distance_km" for pr in new_prs)


async def test_lower_value_no_new_pr(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        await check_and_update_records([make_activity(distance_km=100.0)])
        new_prs = await check_and_update_records([make_activity(distance_km=80.0)])
    assert not any(pr["category"] == "distance_km" for pr in new_prs)


async def test_prs_separated_by_activity_type(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        cycling = make_activity(activity_type="cycling", distance_km=100.0)
        running = make_activity(activity_type="running", distance_km=42.0)
        new_prs = await check_and_update_records([cycling, running])
    types = {pr["activity_type"] for pr in new_prs}
    assert "cycling" in types
    assert "running" in types


async def test_unknown_type_skipped(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        act = Activity(date="2026-03-25", name="Test", activity_type="unknown", distance_km=10.0)
        new_prs = await check_and_update_records([act])
    assert len(new_prs) == 0


async def test_none_values_skipped(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        act = Activity(date="2026-03-25", name="Test", activity_type="cycling")
        new_prs = await check_and_update_records([act])
    assert len(new_prs) == 0


async def test_pr_contains_expected_fields(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        new_prs = await check_and_update_records([make_activity()])
    pr = new_prs[0]
    assert "activity_type" in pr
    assert "category" in pr
    assert "value" in pr
    assert "date" in pr
    assert "previous" in pr


async def test_first_pr_has_none_previous(pr_db):
    with patch("src.storage.database.DB_PATH", pr_db):
        new_prs = await check_and_update_records([make_activity()])
    assert any(pr["previous"] is None for pr in new_prs)

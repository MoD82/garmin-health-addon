import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_build_context_blocks_has_pmc_key(tmp_path):
    """build_context_blocks gibt jetzt blocks['pmc'] zurück."""
    from src.storage.database import init_db
    from src.analysis.tiefenanalyse import build_context_blocks

    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        blocks = await build_context_blocks(days=7)

    assert "pmc" in blocks
    pmc = blocks["pmc"]
    assert "ctl" in pmc
    assert "atl" in pmc
    assert "tsb" in pmc
    assert "recommendation" in pmc
    assert "recommendation_reason" in pmc
    assert "trend" in pmc
    assert "series" in pmc
    assert isinstance(pmc["series"], list)


@pytest.mark.asyncio
async def test_pmc_trend_values(tmp_path):
    """PMC-Trend ist einer von vier gültigen Werten."""
    from src.storage.database import init_db
    from src.analysis.tiefenanalyse import build_context_blocks

    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        blocks = await build_context_blocks(days=14)

    valid_trends = {"aufbauend", "tapering", "stagnierend", "überlastet"}
    assert blocks["pmc"]["trend"] in valid_trends


@pytest.mark.asyncio
async def test_pmc_recommendation_reason_is_string(tmp_path):
    """recommendation_reason ist ein String für GPT-Kontext."""
    from src.storage.database import init_db
    from src.analysis.tiefenanalyse import build_context_blocks

    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()
        blocks = await build_context_blocks(days=7)

    assert isinstance(blocks["pmc"]["recommendation_reason"], str)
    assert len(blocks["pmc"]["recommendation_reason"]) > 0

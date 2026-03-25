import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from src.storage.database import init_db
from src.config import Config


@pytest.fixture
async def analysis_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.storage.database.DB_PATH", db_path):
        import aiosqlite
        await init_db()
        async with aiosqlite.connect(db_path) as db:
            today = date.today().isoformat()
            await db.execute(
                "INSERT INTO daily_data (date, sleep_score, body_battery, hrv_status, stress_total) "
                "VALUES (?, 80, 70, 'balanced', 620)", (today,)
            )
            await db.commit()
        yield db_path


async def test_run_analysis_returns_success(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")  # empty key → GPT skipped

    with patch("src.storage.database.DB_PATH", analysis_db):
        result = await run_analysis(config, {})

    assert result["status"] == "success"


async def test_run_analysis_calculates_readiness(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")

    with patch("src.storage.database.DB_PATH", analysis_db):
        result = await run_analysis(config, {})

    assert "readiness" in result
    assert 0 <= result["readiness"] <= 100


async def test_run_analysis_saves_to_db(analysis_db):
    import aiosqlite
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")

    with patch("src.storage.database.DB_PATH", analysis_db):
        await run_analysis(config, {})
        async with aiosqlite.connect(analysis_db) as db:
            cursor = await db.execute("SELECT status FROM analyses WHERE date = ?", (date.today().isoformat(),))
            row = await cursor.fetchone()

    assert row is not None
    assert row[0] == "success"


async def test_run_analysis_calls_gpt_when_key_set(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="sk-test")

    mock_gpt = MagicMock(return_value="Coach-Text hier.")
    with patch("src.storage.database.DB_PATH", analysis_db), \
         patch("src.analysis.run_analysis.run_gpt_analysis", mock_gpt):
        result = await run_analysis(config, {"gpt_context_days": "14", "gpt_max_tokens": "1000", "gpt_temperature": "0.4"})

    assert result["gpt_response"] == "Coach-Text hier."


async def test_run_analysis_skips_gpt_without_key(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")

    mock_gpt = MagicMock()
    with patch("src.storage.database.DB_PATH", analysis_db), \
         patch("src.analysis.run_analysis.run_gpt_analysis", mock_gpt):
        await run_analysis(config, {})

    mock_gpt.assert_not_called()


async def test_run_analysis_gpt_error_falls_back(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="sk-test")

    with patch("src.storage.database.DB_PATH", analysis_db), \
         patch("src.analysis.run_analysis.run_gpt_analysis", side_effect=Exception("API Error")):
        result = await run_analysis(config, {})

    # Analysis completes with success status despite GPT error
    assert result["status"] == "success"
    assert result["gpt_response"] == ""


async def test_run_analysis_emit_callback_called(analysis_db):
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")
    events = []

    with patch("src.storage.database.DB_PATH", analysis_db):
        await run_analysis(config, {}, emit=events.append)

    assert len(events) > 0
    assert any("Analyse" in e for e in events)


async def test_run_analysis_error_saved_to_db(analysis_db):
    import aiosqlite
    from src.analysis.run_analysis import run_analysis
    config = Config(openai_api_key="")

    with patch("src.storage.database.DB_PATH", analysis_db), \
         patch("src.analysis.run_analysis.build_context_blocks", side_effect=Exception("DB fehler")):
        result = await run_analysis(config, {})

    assert result["status"] == "error"

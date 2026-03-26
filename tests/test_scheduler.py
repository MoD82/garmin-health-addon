import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_run_weekly_report_skips_when_disabled():
    """Wochenbericht wird übersprungen wenn weekly_report_enabled=false."""
    from src.config import Config
    from src.scheduler import _run_weekly_report

    config = Config()

    with patch("src.settings.manager.SettingsManager") as MockMgr:
        mgr = AsyncMock()
        mgr.get = AsyncMock(return_value="false")  # weekly_report_enabled = false
        MockMgr.return_value = mgr

        with patch("src.output.email_sender.send_report", new_callable=AsyncMock) as mock_send:
            await _run_weekly_report(config)

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_run_weekly_report_skips_when_email_disabled():
    """Wochenbericht wird übersprungen wenn output_email=false."""
    from src.config import Config
    from src.scheduler import _run_weekly_report

    config = Config()

    with patch("src.settings.manager.SettingsManager") as MockMgr:
        mgr = AsyncMock()
        mgr.get = AsyncMock(side_effect=lambda k: {
            "weekly_report_enabled": "true",
            "output_email": "false",
        }.get(k, "false"))
        MockMgr.return_value = mgr

        with patch("src.output.email_sender.send_report", new_callable=AsyncMock) as mock_send:
            await _run_weekly_report(config)

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_run_weekly_report_sends_is_weekly_true(tmp_path):
    """_run_weekly_report sendet Email mit is_weekly=True."""
    from src.config import Config
    from src.scheduler import _run_weekly_report
    from src.storage.database import init_db

    config = Config(
        email_user="test@example.com",
        email_password="secret",
        email_recipient="recipient@example.com",
    )
    db_path = tmp_path / "test.db"

    with patch("src.storage.database.DB_PATH", db_path):
        await init_db()

        with patch("src.settings.manager.SettingsManager") as MockMgr:
            mgr = AsyncMock()
            mgr.get = AsyncMock(side_effect=lambda k: {
                "weekly_report_enabled": "true",
                "output_email": "true",
            }.get(k, "false"))
            mgr.get_int = AsyncMock(return_value=14)
            MockMgr.return_value = mgr

            with patch("src.output.email_sender.send_report", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = True
                await _run_weekly_report(config)

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs.get("is_weekly") is True

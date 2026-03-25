import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.config import Config
from src.output.email_sender import send_report, _render_email


def _config(**kwargs) -> Config:
    defaults = dict(
        email_user="test@example.com",
        email_password="secret",
        email_recipient="recipient@example.com",
        email_smtp_host="smtp.example.com",
        email_smtp_port=587,
    )
    defaults.update(kwargs)
    return Config(**defaults)


def _result(**kwargs) -> dict:
    base = dict(
        status="success",
        date="2026-03-25",
        readiness=72,
        gpt_response="Gute Erholung heute.",
        new_prs=[],
    )
    base.update(kwargs)
    return base


def _blocks() -> dict:
    return dict(
        daily=[{
            "date": "2026-03-25", "body_battery": 74, "sleep_score": 83,
            "hrv_status": "balanced", "stress_total": 620, "weight": 78.2,
            "body_fat": 14.1, "muscle_mass": 67.2,
        }],
        activities=[{
            "date": "2026-03-22", "name": "Rennrad Tour", "activity_type": "cycling",
            "distance_km": 87.0, "elevation_m": 1200, "norm_power": 234,
            "tss": 145.0, "duration_min": 180,
        }],
        blood_pressure=[
            {"systolic": 118, "diastolic": 76, "pulse": 64, "measured_at": "2026-03-25 08:00"},
        ],
        events=[{
            "title": "Jedermann 2026", "date_start": "2026-06-15",
            "event_type": "race", "priority": "A",
        }],
        checkin=None,
        personal_records=[],
    )


@pytest.mark.asyncio
async def test_send_report_no_email_config_returns_false():
    """Fehlendes Email-Config → False, kein SMTP-Versuch."""
    config = Config()  # email_user = ""
    result = await send_report(config, _result(), _blocks())
    assert result is False


@pytest.mark.asyncio
async def test_send_report_calls_smtp_success():
    """Korrektes Config → SMTP wird aufgerufen, True zurück."""
    config = _config()
    with patch("src.output.email_sender.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_smtp.sendmail = MagicMock()

        # Template existiert noch nicht → _render_email mocken
        with patch("src.output.email_sender._render_email", return_value="<html>test</html>"):
            result = await send_report(config, _result(), _blocks())

    assert result is True
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("test@example.com", "secret")


@pytest.mark.asyncio
async def test_send_report_smtp_failure_returns_false():
    """SMTP-Fehler → False, kein Exception-Propagation."""
    config = _config()
    with patch("src.output.email_sender.smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
        with patch("src.output.email_sender._render_email", return_value="<html>test</html>"):
            result = await send_report(config, _result(), _blocks())
    assert result is False


@pytest.mark.asyncio
async def test_send_report_weekly_subject_contains_wochenbericht():
    """Wochenbericht → Subject enthält 'Wochenbericht'."""
    config = _config()

    with patch("src.output.email_sender._render_email", return_value="<html>test</html>"):
        with patch("src.output.email_sender._send_smtp") as mock_send:
            await send_report(config, _result(), _blocks(), is_weekly=True)
            call_args = mock_send.call_args
            assert "Wochenbericht" in call_args[0][1]


@pytest.mark.asyncio
async def test_send_report_daily_subject_contains_tagesbericht():
    """Tagesbericht → Subject enthält 'Tagesbericht'."""
    config = _config()

    with patch("src.output.email_sender._render_email", return_value="<html>test</html>"):
        with patch("src.output.email_sender._send_smtp") as mock_send:
            await send_report(config, _result(), _blocks(), is_weekly=False)
            call_args = mock_send.call_args
            assert "Tagesbericht" in call_args[0][1]

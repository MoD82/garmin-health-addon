import pytest
from unittest.mock import MagicMock, patch
from src.analysis.gpt_engine import build_prompt, run_gpt_analysis


def make_blocks(daily=None, activities=None, blood_pressure=None, events=None, personal_records=None):
    return {
        "daily": daily or [],
        "activities": activities or [],
        "blood_pressure": blood_pressure or [],
        "events": events or [],
        "checkin": None,
        "personal_records": personal_records or [],
    }


def test_build_prompt_empty_blocks():
    blocks = make_blocks()
    prompt = build_prompt(blocks, "Montag, 25. März 2026", 14)
    assert "14 Tage" in prompt
    assert isinstance(prompt, str)


def test_build_prompt_includes_daily_data():
    blocks = make_blocks(daily=[{
        "date": "2026-03-25", "sleep_score": 80, "body_battery": 70,
        "hrv_status": "balanced", "stress_total": 620, "readiness_score": 72
    }])
    prompt = build_prompt(blocks, "Montag, 25. März 2026", 14)
    assert "2026-03-25" in prompt
    assert "80" in prompt  # sleep


def test_build_prompt_includes_activities():
    blocks = make_blocks(activities=[{
        "date": "2026-03-25", "activity_type": "cycling",
        "distance_km": 87.0, "norm_power": 234, "tss": 145.0
    }])
    prompt = build_prompt(blocks, "Montag, 25. März 2026", 14)
    assert "cycling" in prompt
    assert "87.0" in prompt


def test_build_prompt_includes_events():
    blocks = make_blocks(events=[{
        "date_start": "2026-06-15", "title": "Jedermann",
        "event_type": "race", "priority": "A"
    }])
    prompt = build_prompt(blocks, "Montag, 25. März 2026", 14)
    assert "Jedermann" in prompt


def test_build_prompt_includes_personal_records():
    blocks = make_blocks(personal_records=[{
        "activity_type": "cycling", "category": "distance_km",
        "value": 87.0, "date": "2026-03-25"
    }])
    prompt = build_prompt(blocks, "Montag, 25. März 2026", 14)
    assert "cycling" in prompt
    assert "distance_km" in prompt


def test_run_gpt_analysis_calls_openai():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Heute: Z2-Ausdauer 90 min empfohlen."
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.analysis.gpt_engine.OpenAI", return_value=mock_client):
        result = run_gpt_analysis(
            api_key="test-key",
            model="gpt-4o",
            blocks=make_blocks(),
            max_tokens=1000,
            temperature=0.4,
            days=14,
        )

    assert result == "Heute: Z2-Ausdauer 90 min empfohlen."
    mock_client.chat.completions.create.assert_called_once()


def test_run_gpt_analysis_passes_correct_params():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Coach-Text"
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.analysis.gpt_engine.OpenAI", return_value=mock_client):
        run_gpt_analysis(
            api_key="test-key", model="gpt-4o-mini",
            blocks=make_blocks(), max_tokens=500, temperature=0.3, days=7,
        )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["max_tokens"] == 500
    assert call_kwargs["temperature"] == 0.3


def test_run_gpt_analysis_raises_on_api_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")

    with patch("src.analysis.gpt_engine.OpenAI", return_value=mock_client):
        with pytest.raises(Exception, match="API Error"):
            run_gpt_analysis(
                api_key="bad-key", model="gpt-4o",
                blocks=make_blocks(), max_tokens=1000, temperature=0.4, days=14,
            )

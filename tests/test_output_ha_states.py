import pytest
from unittest.mock import patch, MagicMock
from datetime import date


def _result(**kwargs):
    return {"status": "success", "date": "2026-03-26",
            "readiness": 72, "gpt_response": "", "new_prs": [], **kwargs}


def _blocks(body_battery=74, events=None):
    return {
        "daily": [{"date": "2026-03-26", "body_battery": body_battery}],
        "activities": [], "blood_pressure": [],
        "events": events or [], "checkin": None, "personal_records": [],
    }


def test_update_ha_sensors_posts_six_entities():
    from src.output.ha_states import update_ha_sensors
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.ha_states.requests.post", return_value=mock_resp) as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test-token"}):
            update_ha_sensors(_result(), _blocks())
    assert mock_post.call_count == 6


def test_update_ha_sensors_readiness_score_correct():
    from src.output.ha_states import update_ha_sensors
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.ha_states.requests.post", return_value=mock_resp) as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            update_ha_sensors(_result(readiness=85), _blocks())
    calls = {c.args[0].split("/")[-1]: c.kwargs["json"]["state"]
             for c in mock_post.call_args_list}
    assert calls["sensor.coach_readiness_score"] == "85"


def test_update_ha_sensors_no_token_skips():
    from src.output.ha_states import update_ha_sensors
    with patch("src.output.ha_states.requests.post") as mock_post:
        with patch.dict("os.environ", {}, clear=True):
            update_ha_sensors(_result(), _blocks())
    mock_post.assert_not_called()


def test_update_ha_sensors_next_race_days():
    from src.output.ha_states import update_ha_sensors
    from datetime import timedelta
    future_date = (date.today() + timedelta(days=15)).isoformat()
    events = [{"event_type": "race", "date_start": future_date, "title": "Jedermann"}]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.ha_states.requests.post", return_value=mock_resp) as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            update_ha_sensors(_result(), _blocks(events=events))
    calls = {c.args[0].split("/")[-1]: c.kwargs["json"]["state"]
             for c in mock_post.call_args_list}
    assert calls["sensor.coach_next_race_days"] == "15"


def test_update_ha_sensors_no_race_returns_minus_one():
    from src.output.ha_states import update_ha_sensors
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.ha_states.requests.post", return_value=mock_resp) as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            update_ha_sensors(_result(), _blocks(events=[]))
    calls = {c.args[0].split("/")[-1]: c.kwargs["json"]["state"]
             for c in mock_post.call_args_list}
    assert calls["sensor.coach_next_race_days"] == "-1"

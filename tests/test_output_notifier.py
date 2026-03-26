import pytest
from unittest.mock import patch, MagicMock


def _settings(**kwargs):
    base = {
        "alert_body_battery_threshold": "30",
        "alert_declining_battery_days": "5",
        "alert_new_pr": "true",
        "alert_race_countdown_days": "7",
        "output_push": "true",
    }
    base.update(kwargs)
    return base


def _result(**kwargs):
    return {"status": "success", "date": "2026-03-26",
            "readiness": 72, "gpt_response": "", "new_prs": [], **kwargs}


def _blocks_with_bb(bb_values: list, events=None, bp=None):
    daily = [{"date": f"2026-03-{26-i:02d}", "body_battery": v}
             for i, v in enumerate(bb_values)]
    return {
        "daily": daily,
        "activities": [],
        "blood_pressure": bp or [],
        "events": events or [],
        "checkin": None,
        "personal_records": [],
    }


def test_no_alerts_when_output_push_disabled():
    from src.output.notifier import send_alerts
    with patch("src.output.notifier.requests.post") as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([74]),
                                 _settings(**{"output_push": "false"}))
    mock_post.assert_not_called()
    assert alerts == []


def test_alert_body_battery_critical():
    from src.output.notifier import send_alerts
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.notifier.requests.post", return_value=mock_resp):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([25]), _settings())
    assert any("Body Battery" in a for a in alerts)


def test_no_alert_when_bb_above_threshold():
    from src.output.notifier import send_alerts
    with patch("src.output.notifier.requests.post") as mock_post:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([74]), _settings())
    assert not any("Body Battery" in a for a in alerts)


def test_alert_declining_battery():
    from src.output.notifier import send_alerts
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.output.notifier.requests.post", return_value=mock_resp):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([40, 45, 50, 55, 60]), _settings())
    assert any("Erholung" in a for a in alerts)


def test_alert_new_pr():
    from src.output.notifier import send_alerts
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    new_prs = [{"activity_type": "cycling", "category": "distance_km", "value": 90.0}]
    with patch("src.output.notifier.requests.post", return_value=mock_resp):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(new_prs=new_prs), _blocks_with_bb([74]), _settings())
    assert any("Bestleistung" in a for a in alerts)


def test_alert_race_countdown():
    from src.output.notifier import send_alerts
    from datetime import date, timedelta
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    future = (date.today() + timedelta(days=5)).isoformat()
    events = [{"event_type": "race", "date_start": future, "title": "Jedermann"}]
    with patch("src.output.notifier.requests.post", return_value=mock_resp):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([74], events=events), _settings())
    assert any("Jedermann" in a for a in alerts)


def test_alert_blood_pressure_high():
    from src.output.notifier import send_alerts
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    bp = [{"systolic": 145, "diastolic": 92, "pulse": 72}]
    with patch("src.output.notifier.requests.post", return_value=mock_resp):
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "tok"}):
            alerts = send_alerts(_result(), _blocks_with_bb([74], bp=bp), _settings())
    assert any("Blutdruck" in a for a in alerts)

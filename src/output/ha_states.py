# src/output/ha_states.py
"""HA-Sensor-Entities via REST API aktualisieren."""
import logging
import os
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

_HA_URL = "http://supervisor/core/api/states"


def _post(entity_id: str, state: str, friendly_name: str) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        logger.warning("SUPERVISOR_TOKEN fehlt — HA-Sensor-Update übersprungen")
        return
    url = f"{_HA_URL}/{entity_id}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"state": str(state), "attributes": {"friendly_name": friendly_name}},
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            logger.warning("HA-Sensor %s: HTTP %s", entity_id, resp.status_code)
    except Exception as exc:
        logger.error("HA-Sensor %s fehlgeschlagen: %s", entity_id, exc)


def _readiness_status(score: int) -> str:
    if score >= 75:
        return "GUT"
    elif score >= 50:
        return "MODERAT"
    return "ERHOLUNG"


def _next_race_days(events: list) -> int:
    today = date.today()
    for ev in events:
        if ev.get("event_type") != "race":
            continue
        date_start = ev.get("date_start", "")
        try:
            race_date = date.fromisoformat(str(date_start)[:10])
            if race_date >= today:
                return (race_date - today).days
        except (ValueError, TypeError):
            continue
    return -1


def update_ha_sensors(result: dict, blocks: dict) -> None:
    """Schreibt 6 HA-Sensor-Entities nach einer Analyse."""
    readiness = result.get("readiness", 0)
    today_data = blocks.get("daily", [{}])[0] if blocks.get("daily") else {}
    body_battery = today_data.get("body_battery", -1) if today_data else -1
    next_race = _next_race_days(blocks.get("events", []))

    _post("sensor.coach_readiness_score", readiness, "Coach Readiness Score")
    _post("sensor.coach_readiness_status", _readiness_status(readiness), "Coach Readiness Status")
    _post("sensor.coach_last_analysis", datetime.now().isoformat(), "Coach Letzte Analyse")
    _post("sensor.coach_analysis_status", result.get("status", "unknown"), "Coach Analyse Status")
    _post("sensor.coach_body_battery", body_battery if body_battery is not None else -1, "Coach Body Battery")
    _post("sensor.coach_next_race_days", next_race, "Coach Nächstes Rennen (Tage)")

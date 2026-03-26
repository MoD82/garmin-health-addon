# src/output/notifier.py
"""Push-Notifications via HA REST API (notify.mobile_app_mods_iphone)."""
import logging
import os
from datetime import date

import requests

logger = logging.getLogger(__name__)

_HA_NOTIFY_URL = "http://supervisor/core/api/services/notify/mobile_app_mods_iphone"


def _send_push(title: str, message: str) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        logger.warning("SUPERVISOR_TOKEN fehlt — Push-Notification übersprungen")
        return
    try:
        resp = requests.post(
            _HA_NOTIFY_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"title": title, "message": message},
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            logger.warning("Push-Notification HTTP %s", resp.status_code)
    except Exception as exc:
        logger.error("Push-Notification fehlgeschlagen: %s", exc)


def _check_declining_battery(daily: list, days: int) -> bool:
    """True wenn BB in den letzten N Tagen durchgehend gesunken ist (neuester zuerst)."""
    bb_values = [d.get("body_battery") for d in daily[:days] if d.get("body_battery") is not None]
    if len(bb_values) < days:
        return False
    return all(bb_values[i] < bb_values[i + 1] for i in range(len(bb_values) - 1))


def _next_race(events: list) -> dict | None:
    today = date.today()
    for ev in events:
        if ev.get("event_type") != "race":
            continue
        try:
            race_date = date.fromisoformat(str(ev.get("date_start", ""))[:10])
            if race_date >= today:
                return {**ev, "_days": (race_date - today).days}
        except (ValueError, TypeError):
            continue
    return None


def send_alerts(result: dict, blocks: dict, settings: dict) -> list[str]:
    """
    Prüft Alert-Schwellwerte und sendet Push-Notifications.
    Returns: Liste der gesendeten Alert-Texte.
    """
    if settings.get("output_push") != "true":
        return []

    alerts: list[str] = []
    daily = blocks.get("daily", [])
    today_data = daily[0] if daily else {}
    body_battery = today_data.get("body_battery") if today_data else None

    # 1. Body Battery kritisch
    bb_threshold = int(settings.get("alert_body_battery_threshold", "30"))
    if body_battery is not None and body_battery < bb_threshold:
        msg = f"⚠️ Body Battery kritisch: {body_battery} — Ruhetag empfohlen"
        _send_push("Garmin Coach", msg)
        alerts.append(msg)

    # 2. Body Battery sinkend
    declining_days = int(settings.get("alert_declining_battery_days", "5"))
    if _check_declining_battery(daily, declining_days):
        msg = f"📉 Erholung unvollständig seit {declining_days} Tagen — Training reduzieren"
        _send_push("Garmin Coach", msg)
        alerts.append(msg)

    # 3. Neue Bestleistungen
    if settings.get("alert_new_pr") == "true":
        for pr in result.get("new_prs", []):
            msg = f"🏆 Neue Bestleistung: {pr.get('category')} {pr.get('value')}"
            _send_push("Garmin Coach", msg)
            alerts.append(msg)

    # 4. Rennen-Countdown
    race_threshold = int(settings.get("alert_race_countdown_days", "7"))
    next_race = _next_race(blocks.get("events", []))
    if next_race and 0 < next_race["_days"] <= race_threshold:
        msg = f"🏁 {next_race['title']} in {next_race['_days']} Tagen — Taper-Woche beginnt"
        _send_push("Garmin Coach", msg)
        alerts.append(msg)

    # 5. Blutdruck erhöht
    bp_list = blocks.get("blood_pressure", [])
    if bp_list:
        latest_bp = bp_list[0]
        sys_val = latest_bp.get("systolic", 0)
        dia_val = latest_bp.get("diastolic", 0)
        if sys_val >= 140 or dia_val >= 90:
            msg = f"🩺 Blutdruck erhöht: {sys_val}/{dia_val} — beobachten"
            _send_push("Garmin Coach", msg)
            alerts.append(msg)

    return alerts

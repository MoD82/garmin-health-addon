"""Tiefenanalyse — Context Blocks aus SQLite für GPT-Analysen."""
from datetime import date, timedelta
from ..storage.database import get_db


async def build_context_blocks(
    days: int = 14,
    include_activities: bool = True,
    include_blood_pressure: bool = True,
) -> dict:
    """
    Liest Daten aus SQLite und gibt strukturierte Blöcke für GPT-Kontext zurück.

    Args:
        days: Anzahl der zurückliegenden Tage (default: 14).
        include_activities: Aktivitätsdaten einbeziehen (default: True).
        include_blood_pressure: Blutdruckdaten einbeziehen (default: True).

    Returns:
        Dict mit Keys: daily, activities, blood_pressure, events, checkin, personal_records.
    """
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()

    async for db in get_db():
        # --- Daily Data ---
        cursor = await db.execute(
            "SELECT * FROM daily_data WHERE date >= ? ORDER BY date DESC",
            (since,),
        )
        daily_rows = await cursor.fetchall()

        # --- Activities ---
        activities = []
        if include_activities:
            cursor = await db.execute(
                "SELECT * FROM activities WHERE date >= ? ORDER BY date DESC",
                (since,),
            )
            activities = [dict(r) for r in await cursor.fetchall()]

        # --- Blood Pressure ---
        bp_data = []
        if include_blood_pressure:
            cursor = await db.execute(
                "SELECT * FROM blood_pressure ORDER BY measured_at DESC LIMIT 10"
            )
            bp_data = [dict(r) for r in await cursor.fetchall()]

        # --- Events ---
        cursor = await db.execute(
            "SELECT * FROM events WHERE date_start >= ? ORDER BY date_start ASC LIMIT 5",
            (today.isoformat(),),
        )
        events = [dict(r) for r in await cursor.fetchall()]

        # --- Check-ins ---
        cursor = await db.execute(
            "SELECT * FROM daily_checkins ORDER BY date DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        checkin = dict(row) if row else None

        # --- Personal Records ---
        cursor = await db.execute(
            "SELECT * FROM personal_records ORDER BY activity_type, category"
        )
        records = [dict(r) for r in await cursor.fetchall()]

        blocks = {
            "daily": [dict(r) for r in daily_rows],
            "activities": activities,
            "blood_pressure": bp_data,
            "events": events,
            "checkin": checkin,
            "personal_records": records,
        }

    # PMC-Block berechnen (lazy imports innerhalb der Funktion — etabliertes Muster)
    from datetime import date as _date
    from .pmc import calculate_pmc
    from .recommendation import get_recommendation

    _today = _date.today()
    _display_start = _today - timedelta(days=days)
    _warmup_start = _display_start - timedelta(days=42)

    # TSS pro Tag mit training_load als Fallback
    async for db in get_db():
        cursor = await db.execute(
            """SELECT date, COALESCE(SUM(COALESCE(tss, training_load, 0)), 0) as daily_tss
               FROM activities
               WHERE date >= ?
               GROUP BY date""",
            (_warmup_start.isoformat(),),
        )
        _tss_rows = await cursor.fetchall()

    _daily_tss = {row[0]: float(row[1]) for row in _tss_rows}

    # PMC mit Warmup, dann Anzeigebereich herausschneiden
    _full_series = calculate_pmc(_daily_tss, _warmup_start, _today)
    _display_series = [p for p in _full_series if p["date"] >= _display_start.isoformat()]

    _today_pmc = _display_series[-1] if _display_series else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    # Heutige Gesundheit für Recovery Score (aus bereits geladenen daily-Daten)
    _today_str = _today.isoformat()
    _today_health = next(
        (d for d in blocks.get("daily", []) if d.get("date") == _today_str), {}
    )

    _rec = get_recommendation(
        tsb=_today_pmc["tsb"],
        readiness=_today_health.get("readiness_score"),
        body_battery=_today_health.get("body_battery"),
        hrv_status=_today_health.get("hrv_status"),
    )

    # PMC-Trend der letzten 7 Tage
    _recent = _display_series[-7:] if len(_display_series) >= 7 else _display_series
    if len(_recent) >= 2:
        _ctl_diff_per_week = (_recent[-1]["ctl"] - _recent[0]["ctl"])
        _atl_last = _recent[-1]["atl"]
        _ctl_last = _recent[-1]["ctl"]
        _ctl_rising = _recent[-1]["ctl"] > _recent[0]["ctl"]
        _tsb_rising = _recent[-1]["tsb"] > _recent[0]["tsb"]
        if _ctl_diff_per_week > 1:
            _trend = "aufbauend"
        elif _atl_last > _ctl_last + 15:
            _trend = "überlastet"
        elif not _ctl_rising and _tsb_rising:
            _trend = "tapering"
        else:
            _trend = "stagnierend"
    else:
        _trend = "stagnierend"

    blocks["pmc"] = {
        "ctl": _today_pmc["ctl"],
        "atl": _today_pmc["atl"],
        "tsb": _today_pmc["tsb"],
        "recommendation": _rec,
        "recommendation_reason": _rec["reason"],  # Für GPT-Kontext direkt zugänglich
        "trend": _trend,
        "series": _display_series,
    }

    return blocks

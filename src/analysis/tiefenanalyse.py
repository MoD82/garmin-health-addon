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

        return {
            "daily": [dict(r) for r in daily_rows],
            "activities": activities,
            "blood_pressure": bp_data,
            "events": events,
            "checkin": checkin,
            "personal_records": records,
        }

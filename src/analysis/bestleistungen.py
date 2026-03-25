import logging
from ..storage.models import Activity
from ..storage.database import get_db

logger = logging.getLogger(__name__)

_TRACKED_FIELDS = ("distance_km", "avg_power", "norm_power", "max_20min_power")


async def check_and_update_records(activities: list[Activity]) -> list[dict]:
    """
    Vergleicht Aktivitäten mit gespeicherten Bestleistungen.
    Aktualisiert personal_records-Tabelle bei neuen PRs.
    Gibt Liste neuer PRs zurück.
    """
    new_prs = []

    async for db in get_db():
        for act in activities:
            if not act.activity_type or act.activity_type == "unknown":
                continue

            for field in _TRACKED_FIELDS:
                value = getattr(act, field, None)
                if value is None:
                    continue

                cursor = await db.execute(
                    "SELECT value FROM personal_records WHERE activity_type = ? AND category = ?",
                    (act.activity_type, field),
                )
                row = await cursor.fetchone()
                previous = row["value"] if row else None

                if previous is None or value > previous:
                    await db.execute(
                        "INSERT OR REPLACE INTO personal_records "
                        "(activity_type, category, value, date) VALUES (?, ?, ?, ?)",
                        (act.activity_type, field, value, act.date),
                    )
                    await db.commit()
                    new_prs.append({
                        "activity_type": act.activity_type,
                        "category": field,
                        "value": value,
                        "date": act.date,
                        "previous": previous,
                    })
                    logger.info(
                        "Neue Bestleistung: %s / %s = %s (vorher: %s)",
                        act.activity_type, field, value, previous,
                    )

    return new_prs

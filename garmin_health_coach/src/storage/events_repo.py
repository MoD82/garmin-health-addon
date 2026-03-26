"""CRUD-Operationen für die events-Tabelle."""
from .database import get_db


class EventsRepo:
    async def create(self, data: dict) -> int:
        """Legt neues Event an. Gibt neue ID zurück."""
        async for db in get_db():
            cursor = await db.execute(
                """INSERT INTO events
                   (event_type, date_start, date_end, title, priority,
                    distance_km, elevation_m, goal, training_possible, status)
                   VALUES (:event_type, :date_start, :date_end, :title, :priority,
                           :distance_km, :elevation_m, :goal, :training_possible, :status)""",
                {
                    "event_type": data.get("event_type", "note"),
                    "date_start": data.get("date_start", ""),
                    "date_end": data.get("date_end"),
                    "title": data.get("title", ""),
                    "priority": data.get("priority"),
                    "distance_km": data.get("distance_km"),
                    "elevation_m": data.get("elevation_m"),
                    "goal": data.get("goal"),
                    "training_possible": 1 if data.get("training_possible", True) else 0,
                    "status": data.get("status", "planned"),
                },
            )
            await db.commit()
            return cursor.lastrowid

    async def get(self, event_id: int) -> dict | None:
        """Gibt ein Event zurück oder None."""
        async for db in get_db():
            cursor = await db.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_all(self) -> list[dict]:
        """Alle Events aufsteigend nach date_start sortiert."""
        async for db in get_db():
            cursor = await db.execute(
                "SELECT * FROM events ORDER BY date_start ASC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def list_for_month(self, year: int, month: int) -> list[dict]:
        """Events die in einen Monat fallen (date_start im Monat)."""
        prefix = f"{year}-{month:02d}"
        async for db in get_db():
            cursor = await db.execute(
                "SELECT * FROM events WHERE date_start LIKE ? ORDER BY date_start ASC",
                (f"{prefix}%",),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update(self, event_id: int, data: dict) -> None:
        """Aktualisiert vorhandene Felder eines Events."""
        allowed = {"event_type", "date_start", "date_end", "title", "priority",
                   "distance_km", "elevation_m", "goal", "training_possible", "status"}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = event_id
        async for db in get_db():
            await db.execute(
                f"UPDATE events SET {set_clause} WHERE id = :id", fields
            )
            await db.commit()

    async def delete(self, event_id: int) -> None:
        async for db in get_db():
            await db.execute("DELETE FROM events WHERE id = ?", (event_id,))
            await db.commit()

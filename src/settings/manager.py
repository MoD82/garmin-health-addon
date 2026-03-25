from ..storage.database import get_db

DEFAULTS: dict[str, str] = {
    "gpt_context_days": "14",
    "gpt_include_activities": "true",
    "gpt_include_blood_pressure": "true",
    "gpt_include_body_composition": "true",
    "gpt_max_tokens": "1000",
    "gpt_temperature": "0.4",
    "analysis_mode": "manual",
    "analysis_time": "08:00",
    "weekly_report_enabled": "false",
    "weekly_report_day": "monday",
    "output_email": "true",
    "output_push": "true",
    "output_ha_sensor": "true",
    "alert_body_battery_threshold": "30",
    "alert_declining_battery_days": "5",
    "alert_new_pr": "true",
    "alert_race_countdown_days": "7",
    "collection_mode": "auto",
    "collection_time": "07:30",
}


class SettingsManager:
    async def get(self, key: str) -> str:
        async for db in get_db():
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            return row["value"] if row else DEFAULTS.get(key, "")

    async def set(self, key: str, value: str) -> None:
        async for db in get_db():
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
            await db.commit()

    async def get_all(self) -> dict[str, str]:
        result = dict(DEFAULTS)
        async for db in get_db():
            cursor = await db.execute("SELECT key, value FROM settings")
            rows = await cursor.fetchall()
            for row in rows:
                result[row["key"]] = row["value"]
        return result

    async def get_int(self, key: str) -> int:
        return int(await self.get(key))

    async def get_bool(self, key: str) -> bool:
        return (await self.get(key)).lower() == "true"

    async def get_float(self, key: str) -> float:
        return float(await self.get(key))

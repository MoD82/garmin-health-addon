"""Aktivitäten-Collector — Garmin API → activities Tabelle (UPSERT)."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import aiosqlite

from src.collector.garmin_client import GarminClient
from src.storage.database import DB_PATH
from src.storage.models import Activity

logger = logging.getLogger(__name__)

ACTIVITY_TYPE_MAP: dict[str, str] = {
    "cycling": "cycling",
    "road_biking": "cycling",
    "mountain_biking": "cycling",
    "gravel_cycling": "cycling",
    "indoor_cycling": "cycling",
    "virtual_ride": "cycling",
    "running": "running",
    "trail_running": "running",
    "treadmill_running": "running",
    "swimming": "swimming",
    "open_water_swimming": "swimming",
    "lap_swimming": "swimming",
    "hiking": "hiking",
    "walking": "hiking",
}

LOOKBACK_DAYS = 2


def map_activity(raw: dict) -> Activity:
    """Konvertiert Garmin-Aktivitäts-Dict in Activity Pydantic Model.

    Args:
        raw: Einzel-Aktivität aus get_activities_by_date().

    Returns:
        Activity Instanz.
    """
    type_key = raw.get("activityType", {}).get("typeKey", "")
    activity_type = ACTIVITY_TYPE_MAP.get(type_key, "other")

    start_raw = raw.get("startTimeLocal", "")
    try:
        activity_date = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S").date()
    except (ValueError, TypeError):
        activity_date = date.today()

    distance_raw = raw.get("distance")
    distance_km = round(distance_raw / 1000, 2) if distance_raw is not None else None

    duration_raw = raw.get("duration")
    duration_min = round(duration_raw / 60) if duration_raw is not None else None

    return Activity(
        date=activity_date,
        name=raw.get("activityName", "Unbekannte Aktivität"),
        activity_type=activity_type,
        distance_km=distance_km,
        duration_min=duration_min,
        elevation_m=raw.get("elevationGain"),
        avg_hr=raw.get("averageHR"),
        max_hr=raw.get("maxHR"),
        avg_power=raw.get("avgPower"),
        max_power=raw.get("maxPower"),
        norm_power=raw.get("normPower"),
        tss=raw.get("trainingStressScore"),
        intensity_factor=raw.get("intensityFactor"),
        aero_te=raw.get("aerobicTrainingEffect"),
        anaero_te=raw.get("anaerobicTrainingEffect"),
        training_load=raw.get("activityTrainingLoad"),
    )


class ActivityCollector:
    """Sammelt Aktivitäten der letzten LOOKBACK_DAYS Tage."""

    async def collect(
        self,
        client: GarminClient,
        today: str,
    ) -> list[Activity]:
        """Holt Aktivitäten und speichert per UPSERT.

        Args:
            client: Eingeloggter GarminClient.
            today:  Datum YYYY-MM-DD (Ende des Abfragefensters).

        Returns:
            Liste gespeicherter Activity-Instanzen (leer bei Fehler).
        """
        end = date.fromisoformat(today)
        start = end - timedelta(days=LOOKBACK_DAYS)

        try:
            raw_list = client.api.get_activities_by_date(
                str(start), str(end)
            ) or []
        except Exception as exc:
            logger.warning(
                "get_activities_by_date() fehlgeschlagen (%s..%s): %s",
                start, end, exc,
            )
            return []

        saved: list[Activity] = []
        for raw in raw_list:
            try:
                activity = map_activity(raw)
                garmin_id = raw.get("activityId")
                await self._upsert(activity, garmin_id)
                saved.append(activity)
            except Exception as exc:
                logger.warning("Aktivität konnte nicht gespeichert werden: %s", exc)

        logger.info(
            "%d Aktivitäten gespeichert (%s..%s)",
            len(saved), start, end,
        )
        return saved

    async def _upsert(self, activity: Activity, garmin_id: Optional[int]) -> None:
        """INSERT OR REPLACE in activities Tabelle.

        Nutzt garmin_id als natürlichen Schlüssel (gespeichert in id-Spalte)
        um Duplikate zu vermeiden.
        """
        async with aiosqlite.connect(DB_PATH) as db:
            if garmin_id:
                # Prüfen ob schon vorhanden
                cursor = await db.execute(
                    "SELECT id FROM activities WHERE id=?", (garmin_id,)
                )
                existing = await cursor.fetchone()
                if existing:
                    logger.debug("Aktivität %d bereits vorhanden — übersprungen", garmin_id)
                    return

            await db.execute(
                """
                INSERT INTO activities (
                    id, date, name, activity_type,
                    distance_km, duration_min, elevation_m,
                    avg_hr, max_hr, avg_power, max_power, norm_power,
                    tss, intensity_factor, aero_te, anaero_te, training_load
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    activity_type=excluded.activity_type,
                    distance_km=excluded.distance_km,
                    duration_min=excluded.duration_min,
                    elevation_m=excluded.elevation_m,
                    avg_hr=excluded.avg_hr,
                    max_hr=excluded.max_hr,
                    avg_power=excluded.avg_power,
                    max_power=excluded.max_power,
                    norm_power=excluded.norm_power,
                    tss=excluded.tss,
                    intensity_factor=excluded.intensity_factor,
                    aero_te=excluded.aero_te,
                    anaero_te=excluded.anaero_te,
                    training_load=excluded.training_load
                """,
                (
                    garmin_id,
                    str(activity.date),
                    activity.name,
                    activity.activity_type,
                    activity.distance_km,
                    activity.duration_min,
                    activity.elevation_m,
                    activity.avg_hr,
                    activity.max_hr,
                    activity.avg_power,
                    activity.max_power,
                    activity.norm_power,
                    activity.tss,
                    activity.intensity_factor,
                    activity.aero_te,
                    activity.anaero_te,
                    activity.training_load,
                ),
            )
            await db.commit()

"""Gesundheitsdaten-Collector — Garmin API → daily_data Tabelle."""
import logging
from datetime import date
from typing import Optional

import aiosqlite

from src.collector.garmin_client import GarminClient
from src.storage.database import DB_PATH
from src.storage.models import DailyData

logger = logging.getLogger(__name__)


def map_stats_to_daily_data(
    date_str: str,
    stats: dict,
    sleep: dict,
    hrv: dict,
    body_comp: dict,
) -> DailyData:
    """Mappt Garmin-API-Dicts auf DailyData-Pydantic-Model.

    Args:
        date_str: Datum im Format YYYY-MM-DD.
        stats:      Antwort von client.get_stats().
        sleep:      Antwort von client.get_sleep_data().
        hrv:        Antwort von client.get_hrv_data().
        body_comp:  Antwort von client.get_body_composition().

    Returns:
        DailyData Instanz — fehlende Felder bleiben None.
    """
    # --- Body Battery ---
    charged = stats.get("bodyBatteryChargedValue")
    drained = stats.get("bodyBatteryDrainedValue")

    # --- Stress ---
    stress_total = stats.get("averageStressLevel")
    stress_high: Optional[int] = None
    high_dur = stats.get("highStressDuration")
    total_dur = stats.get("totalStressDuration")
    if high_dur is not None and total_dur and total_dur > 0:
        stress_high = round((high_dur / total_dur) * 100)

    # --- Sleep ---
    sleep_score: Optional[int] = None
    try:
        sleep_score = (
            sleep.get("dailySleepDTO", {})
            .get("sleepScores", {})
            .get("overall", {})
            .get("value")
        )
    except (AttributeError, TypeError):
        pass

    # --- HRV ---
    hrv_status: Optional[str] = None
    try:
        hrv_status = hrv.get("hrvSummary", {}).get("status")
    except (AttributeError, TypeError):
        pass

    # --- Body Composition (Garmin liefert Gewicht in Gramm) ---
    weight_raw = body_comp.get("weight")
    weight_kg = round(weight_raw / 1000, 2) if weight_raw is not None else None

    muscle_raw = body_comp.get("muscleMass")
    muscle_kg = round(muscle_raw / 1000, 2) if muscle_raw is not None else None

    return DailyData(
        date=date.fromisoformat(date_str),
        body_battery_charged=charged,
        body_battery_drained=drained,
        sleep_score=sleep_score,
        hrv_status=hrv_status,
        stress_total=stress_total,
        stress_high=stress_high,
        vo2max=stats.get("vo2MaxValue"),
        weight=weight_kg,
        body_fat=body_comp.get("bodyFat"),
        muscle_mass=muscle_kg,
        spo2=stats.get("averageSpO2"),
        spo2_lowest=stats.get("lowestSpO2"),
        respiration=stats.get("averageRespirationValue"),
    )


class HealthCollector:
    """Sammelt tägliche Gesundheitsdaten von Garmin und schreibt in SQLite."""

    async def collect(
        self,
        client: GarminClient,
        date_str: str,
    ) -> Optional[DailyData]:
        """Holt Garmin-Daten für date_str und speichert in daily_data.

        Args:
            client:   Eingeloggter GarminClient.
            date_str: Datum YYYY-MM-DD (normalerweise heute).

        Returns:
            DailyData bei Erfolg, None bei API-Fehler (graceful degradation).
        """
        stats, sleep, hrv, body_comp = {}, {}, {}, {}

        # Jeden API-Call einzeln absichern — partieller Ausfall ist ok
        try:
            stats = client.api.get_stats(date_str) or {}
            logger.debug("Stats geladen für %s", date_str)
        except Exception as exc:
            logger.warning("get_stats() fehlgeschlagen: %s", exc)

        try:
            sleep = client.api.get_sleep_data(date_str) or {}
        except Exception as exc:
            logger.warning("get_sleep_data() fehlgeschlagen: %s", exc)

        try:
            hrv = client.api.get_hrv_data(date_str) or {}
        except Exception as exc:
            logger.warning("get_hrv_data() fehlgeschlagen: %s", exc)

        try:
            body_comp = client.api.get_body_composition(date_str) or {}
        except Exception as exc:
            logger.warning("get_body_composition() fehlgeschlagen: %s", exc)

        # Wenn alle Calls fehlgeschlagen → None
        if not any([stats, sleep, hrv, body_comp]):
            logger.warning("Alle Garmin-Health-Calls fehlgeschlagen für %s — übersprungen", date_str)
            return None

        daily = map_stats_to_daily_data(date_str, stats, sleep, hrv, body_comp)
        await self._save(daily)
        logger.info("Gesundheitsdaten gespeichert: %s", date_str)
        return daily

    async def _save(self, data: DailyData) -> None:
        """UPSERT in daily_data Tabelle."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO daily_data (
                    date, body_battery, body_battery_charged, body_battery_drained,
                    sleep_score, hrv_status, stress_total, stress_high,
                    vo2max, weight, body_fat, muscle_mass,
                    spo2, spo2_lowest, respiration, readiness_score
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(date) DO UPDATE SET
                    body_battery=excluded.body_battery,
                    body_battery_charged=excluded.body_battery_charged,
                    body_battery_drained=excluded.body_battery_drained,
                    sleep_score=excluded.sleep_score,
                    hrv_status=excluded.hrv_status,
                    stress_total=excluded.stress_total,
                    stress_high=excluded.stress_high,
                    vo2max=excluded.vo2max,
                    weight=excluded.weight,
                    body_fat=excluded.body_fat,
                    muscle_mass=excluded.muscle_mass,
                    spo2=excluded.spo2,
                    spo2_lowest=excluded.spo2_lowest,
                    respiration=excluded.respiration,
                    readiness_score=excluded.readiness_score
                """,
                (
                    str(data.date),
                    data.body_battery,
                    data.body_battery_charged,
                    data.body_battery_drained,
                    data.sleep_score,
                    data.hrv_status,
                    data.stress_total,
                    data.stress_high,
                    data.vo2max,
                    data.weight,
                    data.body_fat,
                    data.muscle_mass,
                    data.spo2,
                    data.spo2_lowest,
                    data.respiration,
                    data.readiness_score,
                ),
            )
            await db.commit()

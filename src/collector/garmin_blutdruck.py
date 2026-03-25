"""Blutdruck-Collector — Garmin API → blood_pressure Tabelle."""
import logging
from datetime import datetime
from typing import Optional

import aiosqlite

from src.collector.garmin_client import GarminClient
from src.storage.database import DB_PATH
from src.storage.models import BloodPressure

logger = logging.getLogger(__name__)


def _parse_measurement(raw: dict) -> Optional[BloodPressure]:
    """Parst eine Garmin-Blutdruckmessung.

    Args:
        raw: Einzelmessung aus get_blood_pressure().

    Returns:
        BloodPressure Instanz oder None bei unvollständigen Daten.
    """
    try:
        measured_at_str = raw.get("measurementTimestampLocal") or raw.get("measurementTimestamp")
        if not measured_at_str:
            return None
        # Garmin liefert z.B. "2026-03-25T08:12:00.0" — normalisieren
        measured_at_str = measured_at_str.replace("T", " ").split(".")[0]
        measured_at = datetime.strptime(measured_at_str, "%Y-%m-%d %H:%M:%S")

        return BloodPressure(
            measured_at=measured_at,
            systolic=int(raw["systolic"]),
            diastolic=int(raw["diastolic"]),
            pulse=int(raw["pulse"]),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.debug("Messung übersprungen (unvollständige Daten): %s", exc)
        return None


class BlutdruckCollector:
    """Sammelt Blutdruckwerte und speichert nur neue Messungen."""

    async def collect(
        self,
        client: GarminClient,
        date_str: str,
    ) -> list[BloodPressure]:
        """Holt Blutdruckwerte für date_str und speichert neue Einträge.

        Args:
            client:   Eingeloggter GarminClient.
            date_str: Datum YYYY-MM-DD.

        Returns:
            Liste neu gespeicherter BloodPressure-Instanzen.
        """
        try:
            raw_list = client.api.get_blood_pressure(date_str) or []
        except Exception as exc:
            logger.warning("get_blood_pressure() fehlgeschlagen: %s", exc)
            return []

        saved: list[BloodPressure] = []
        for raw in raw_list:
            measurement = _parse_measurement(raw)
            if measurement is None:
                continue
            if await self._already_exists(measurement.measured_at):
                logger.debug("Blutdruck %s bereits vorhanden", measurement.measured_at)
                continue
            await self._save(measurement)
            saved.append(measurement)

        if saved:
            logger.info("%d neue Blutdruckmessungen gespeichert", len(saved))
        return saved

    async def _already_exists(self, measured_at: datetime) -> bool:
        """Prüft ob Messzeitpunkt bereits in DB."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id FROM blood_pressure WHERE measured_at=?",
                (str(measured_at),),
            )
            return await cursor.fetchone() is not None

    async def _save(self, bp: BloodPressure) -> None:
        """INSERT neue Blutdruckmessung."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO blood_pressure (measured_at, systolic, diastolic, pulse) VALUES (?,?,?,?)",
                (str(bp.measured_at), bp.systolic, bp.diastolic, bp.pulse),
            )
            await db.commit()

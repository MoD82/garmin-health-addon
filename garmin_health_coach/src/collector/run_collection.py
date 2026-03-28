"""Orchestrator — ruft alle Collector nacheinander auf, mit Retry."""
import asyncio
import logging
from datetime import date

from src.collector.garmin_client import GarminClient, MFAPendingError
from src.collector.garmin_health import HealthCollector
from src.collector.garmin_activities import ActivityCollector
from src.collector.garmin_blutdruck import BlutdruckCollector
from src.config import Config

logger = logging.getLogger(__name__)


async def collect_all(config: Config) -> dict:
    """Führt komplette Datensammlung durch.

    Retry-Logik: Bei Fehler wird retry_count × retry_interval_minutes gewartet.
    Bei MFAPendingError wird sofort abgebrochen (User-Input nötig).

    Args:
        config: App-Konfiguration mit Garmin-Credentials und Retry-Einstellungen.

    Returns:
        Status-Dict: {"status": "success"|"mfa_pending"|"error", "details": ...}
    """
    today = str(date.today())
    last_error = None

    for attempt in range(1, config.retry_count + 1):
        try:
            logger.info("Datensammlung Versuch %d/%d für %s", attempt, config.retry_count, today)

            client = GarminClient(
                email=config.garmin_user,
                password=config.garmin_password,
            )
            client.ensure_logged_in()

            health_collector = HealthCollector()
            activity_collector = ActivityCollector()
            blutdruck_collector = BlutdruckCollector()

            daily = await health_collector.collect(client, today)
            activities = await activity_collector.collect(client, today)
            blutdruck = await blutdruck_collector.collect(client, today)

            logger.info(
                "Datensammlung erfolgreich: %s | Aktivitäten: %d | Blutdruck: %d",
                today,
                len(activities),
                len(blutdruck),
            )
            return {
                "status": "success",
                "date": today,
                "daily_data": daily is not None,
                "activities_count": len(activities),
                "blood_pressure_count": len(blutdruck),
            }

        except MFAPendingError:
            logger.warning("MFA erforderlich — Datensammlung pausiert bis Code eingegeben wird")
            return {"status": "mfa_pending", "date": today}

        except Exception as exc:
            last_error = exc
            logger.warning("Datensammlung Fehler (Versuch %d): %s", attempt, exc)
            if "429" in str(exc):
                logger.warning("Rate-limited (429) — kein Retry, um Sperre nicht zu verlängern")
                break
            if attempt < config.retry_count:
                wait_sec = config.retry_interval_minutes * 60
                logger.info("Warte %d Minuten bis Retry...", config.retry_interval_minutes)
                await asyncio.sleep(wait_sec)

    logger.error("Datensammlung nach %d Versuchen fehlgeschlagen: %s", config.retry_count, last_error)
    return {"status": "error", "date": today, "error": str(last_error)}

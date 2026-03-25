import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .config import Config

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


def start_scheduler(config: Config) -> None:
    tz = ZoneInfo(config.timezone)
    h_col, m_col = map(int, config.collection_time.split(":"))
    h_ana, m_ana = map(int, config.analysis_time.split(":"))
    h_week, m_week = map(int, config.weekly_report_time.split(":"))
    day_abbr = config.weekly_report_day.lower()[:3]

    _scheduler.add_job(
        _run_collection, CronTrigger(hour=h_col, minute=m_col, timezone=tz),
        id="collection", args=[config], replace_existing=True,
    )
    _scheduler.add_job(
        _run_analysis, CronTrigger(hour=h_ana, minute=m_ana, timezone=tz),
        id="analysis", args=[config], replace_existing=True,
    )
    _scheduler.add_job(
        _run_weekly_report,
        CronTrigger(day_of_week=day_abbr, hour=h_week, minute=m_week, timezone=tz),
        id="weekly_report", args=[config], replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler aktiv | Collection: %s | Analyse: %s | Wochenbericht: %s %s",
        config.collection_time, config.analysis_time,
        config.weekly_report_day, config.weekly_report_time,
    )


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler gestoppt")


def trigger_collection_now(config: Config) -> None:
    _scheduler.add_job(_run_collection, trigger="date", args=[config],
                       id="collection_manual", replace_existing=True)


def trigger_analysis_now(config: Config) -> None:
    _scheduler.add_job(_run_analysis, trigger="date", args=[config],
                       id="analysis_manual", replace_existing=True)


async def _run_collection(config: Config) -> None:
    """Startet Garmin-Datensammlung über Orchestrator."""
    from .collector.run_collection import collect_all
    result = await collect_all(config)
    if result["status"] == "mfa_pending":
        logger.warning("MFA-Eingabe via Web-UI erforderlich: /manual")
    elif result["status"] == "error":
        logger.error("Datensammlung fehlgeschlagen: %s", result.get("error"))
    else:
        logger.info("Datensammlung abgeschlossen: %s", result)


async def _run_analysis(config: Config) -> None:
    logger.info("Analyse gestartet (Phase 3)")


async def _run_weekly_report(config: Config) -> None:
    logger.info("Wochenbericht gestartet (Phase 4)")

import asyncio
import logging
from datetime import date
from typing import Callable

from ..config import Config
from ..storage.database import get_db
from ..storage.models import DailyData, Activity
from .readiness import calculate_readiness
from .tiefenanalyse import build_context_blocks
from .bestleistungen import check_and_update_records
from .gpt_engine import run_gpt_analysis

logger = logging.getLogger(__name__)
Emit = Callable[[str], None]


async def run_analysis(
    config: Config,
    settings: dict,
    emit: Emit | None = None,
) -> dict:
    """
    Vollständiger Analyse-Durchlauf.

    Schritte: Readiness → Context Blocks → Personal Records → GPT → Persistenz
    emit: optionaler Callback für SSE-Fortschritts-Events
    """

    def _emit(msg: str) -> None:
        logger.info(msg)
        if emit:
            emit(msg)

    today = date.today().isoformat()
    _emit(f"Analyse gestartet für {today}")

    try:
        # 1. Readiness Score
        readiness = 0
        row = None
        async for db in get_db():
            cursor = await db.execute(
                "SELECT * FROM daily_data WHERE date = ?", (today,)
            )
            row = await cursor.fetchone()

        if row:
            data = DailyData(**dict(row))
            readiness = calculate_readiness(data)
            _emit(f"Readiness Score: {readiness}/100")
        else:
            _emit("Keine Gesundheitsdaten für heute — Readiness = 0")

        # 2. Context Blocks laden
        days = int(settings.get("gpt_context_days", "14"))
        _emit(f"Lade Kontext ({days} Tage)...")
        blocks = await build_context_blocks(
            days=days,
            include_activities=settings.get("gpt_include_activities", "true") == "true",
            include_blood_pressure=settings.get("gpt_include_blood_pressure", "true") == "true",
        )
        _emit(
            f"Kontext: {len(blocks['daily'])} Tage, "
            f"{len(blocks['activities'])} Aktivitäten"
        )

        # 3. Personal Records prüfen
        _emit("Prüfe Bestleistungen...")
        new_prs: list[dict] = []
        if blocks["activities"]:
            activities = [Activity(**a) for a in blocks["activities"]]
            new_prs = await check_and_update_records(activities)
            if new_prs:
                _emit(f"{len(new_prs)} neue Bestleistung(en)!")
            else:
                _emit("Keine neuen Bestleistungen")

        # 4. GPT-Analyse
        gpt_response = ""
        if config.openai_api_key:
            _emit("GPT-Analyse läuft...")
            try:
                gpt_response = await asyncio.to_thread(
                    run_gpt_analysis,
                    config.openai_api_key,
                    config.openai_model,
                    blocks,
                    int(settings.get("gpt_max_tokens", "1000")),
                    float(settings.get("gpt_temperature", "0.4")),
                    days,
                )
                _emit("GPT-Analyse abgeschlossen")
            except Exception as exc:
                logger.error("GPT-Fehler: %s", exc)
                _emit(f"GPT-Fehler: {exc} — Analyse ohne Coach-Text")

        # 5. Readiness in daily_data speichern
        async for db in get_db():
            await db.execute(
                "UPDATE daily_data SET readiness_score = ? WHERE date = ?",
                (readiness, today),
            )
            await db.commit()

        # 6. Analyse in SQLite speichern
        async for db in get_db():
            await db.execute(
                """INSERT OR REPLACE INTO analyses
                   (date, readiness_score, gpt_response, status)
                   VALUES (?, ?, ?, 'success')""",
                (today, readiness, gpt_response),
            )
            await db.commit()
        _emit("Analyse gespeichert")

        # 7. E-Mail-Versand
        email_sent = False
        if settings.get("output_email") == "true":
            _emit("Versende E-Mail-Report...")
            from ..output.email_sender import send_report
            email_sent = await send_report(config, {
                "status": "success",
                "date": today,
                "readiness": readiness,
                "gpt_response": gpt_response,
                "new_prs": new_prs,
            }, blocks)
            _emit("E-Mail versendet ✓" if email_sent else "E-Mail-Versand übersprungen")

        result = {
            "status": "success",
            "date": today,
            "readiness": readiness,
            "gpt_response": gpt_response,
            "new_prs": new_prs,
            "email_sent": email_sent,
        }
        _emit("Analyse abgeschlossen!")
        return result

    except Exception as exc:
        logger.error("Analyse fehlgeschlagen: %s", exc)
        try:
            async for db in get_db():
                await db.execute(
                    """INSERT OR REPLACE INTO analyses (date, status, error_message)
                       VALUES (?, 'error', ?)""",
                    (today, str(exc)),
                )
                await db.commit()
        except Exception:
            pass
        _emit(f"Fehler: {exc}")
        return {"status": "error", "error": str(exc), "date": today}

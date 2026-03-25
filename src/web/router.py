"""Web-Routen — Dashboard, Manual/MFA-Seite, Collection-Trigger."""
import asyncio
import logging
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "title": "Dashboard"}
    )


@router.get("/manual", response_class=HTMLResponse)
async def manual_page(request: Request):
    """Zeigt MFA-Eingabe falls nötig, sonst manuellen Collection-Trigger."""
    mfa_pending = getattr(request.app.state, "mfa_pending", False)
    mfa_error = getattr(request.app.state, "mfa_error", None)
    last_collection = getattr(request.app.state, "last_collection", None)
    last_analysis = getattr(request.app.state, "last_analysis", None)
    return templates.TemplateResponse(
        "manual.html",
        {
            "request": request,
            "title": "Manuell",
            "mfa_pending": mfa_pending,
            "mfa_error": mfa_error,
            "last_collection": last_collection,
            "last_analysis": last_analysis,
        },
    )


@router.post("/garmin/mfa")
async def submit_mfa(request: Request, mfa_code: str = Form(...)):
    """Verarbeitet MFA-Code-Eingabe aus Web-UI."""
    config = request.app.state.config
    from src.collector.garmin_client import GarminClient

    try:
        client = GarminClient(
            email=config.garmin_user,
            password=config.garmin_password,
        )
        client.ensure_logged_in()
        client.submit_mfa(mfa_code)
        request.app.state.mfa_pending = False
        request.app.state.mfa_error = None
        logger.info("MFA erfolgreich eingegeben")

        # Sofortige Datensammlung nach MFA
        from src.collector.run_collection import collect_all
        import asyncio
        asyncio.create_task(collect_all(config))

    except Exception as exc:
        logger.error("MFA-Fehler: %s", exc)
        request.app.state.mfa_pending = True
        request.app.state.mfa_error = str(exc)

    return RedirectResponse(url="/manual", status_code=303)


@router.post("/garmin/collect")
async def trigger_collection(request: Request):
    """Startet manuelle Datensammlung sofort."""
    from src.scheduler import trigger_collection_now
    config = request.app.state.config
    trigger_collection_now(config)
    logger.info("Manuelle Datensammlung ausgelöst")
    return RedirectResponse(url="/manual", status_code=303)


@router.post("/analysis/trigger")
async def trigger_analysis(request: Request):
    """Startet manuell eine Analyse (SSE-fähig via /analysis/stream)."""
    if getattr(request.app.state, "analysis_running", False):
        logger.info("Analyse läuft bereits — zweiten Start ignoriert")
        return RedirectResponse(url="/manual", status_code=303)

    from src.settings.manager import SettingsManager
    from src.analysis.run_analysis import run_analysis

    settings = await SettingsManager().get_all()
    config = request.app.state.config

    queue: asyncio.Queue = asyncio.Queue()
    request.app.state.analysis_queue = queue
    request.app.state.analysis_running = True
    request.app.state.analysis_log = []

    def emit(msg: str) -> None:
        request.app.state.analysis_log.append(msg)
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    async def run_analysis_task() -> None:
        try:
            result = await run_analysis(config, settings, emit)
            request.app.state.last_analysis = result
        finally:
            request.app.state.analysis_running = False
            queue.put_nowait(None)  # Sentinel: SSE beenden

    asyncio.create_task(run_analysis_task())
    logger.info("Analyse-Task gestartet")
    return RedirectResponse(url="/manual", status_code=303)


@router.get("/analysis/stream")
async def analysis_stream(request: Request):
    """SSE-Endpoint: streamt Analyse-Fortschritt live."""

    async def generate():
        # Bereits vorhandene Logs senden (falls Analyse schon läuft)
        for msg in getattr(request.app.state, "analysis_log", []):
            yield f"data: {msg}\n\n"

        queue = getattr(request.app.state, "analysis_queue", None)
        if queue is None:
            yield "data: Keine Analyse aktiv\n\n"
            return

        # Live-Events streamen bis Sentinel (None)
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield "data: ping\n\n"
                continue
            if msg is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    from src.settings.manager import SettingsManager
    mgr = SettingsManager()
    settings = await mgr.get_all()
    saved = request.query_params.get("saved") == "1"
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "title": "Einstellungen", "settings": settings, "saved": saved},
    )


@router.post("/settings")
async def save_settings(request: Request):
    from src.settings.manager import SettingsManager, DEFAULTS
    mgr = SettingsManager()
    form = await request.form()
    for key in DEFAULTS:
        if key in form:
            await mgr.set(key, str(form[key]))
    logger.info("Einstellungen gespeichert")
    return RedirectResponse(url="/settings?saved=1", status_code=303)

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


def _redirect(request: Request, path: str) -> RedirectResponse:
    """RedirectResponse mit Ingress-Basispfad-Prefix."""
    base = request.scope.get("root_path", "")
    return RedirectResponse(url=f"{base}{path}", status_code=303)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from datetime import date, timedelta
    from ..storage.database import get_db
    from ..analysis.pmc import calculate_pmc
    from ..analysis.recommendation import get_recommendation

    today_str = date.today().isoformat()
    warmup_start = date.today() - timedelta(days=42 + 90)

    async for db in get_db():
        # TSS für PMC (90 Tage Anzeige + 42 Warmup)
        cursor = await db.execute(
            """SELECT date, COALESCE(SUM(COALESCE(tss, training_load, 0)), 0)
               FROM activities WHERE date >= ? GROUP BY date""",
            (warmup_start.isoformat(),),
        )
        tss_rows = await cursor.fetchall()

        # Heutige Gesundheit (nur vorhandene Spalten!)
        cursor = await db.execute(
            """SELECT readiness_score, sleep_score, body_battery, hrv_status, stress_total, vo2max
               FROM daily_data WHERE date = ?""",
            (today_str,),
        )
        health_row = await cursor.fetchone()

        # Letzte Aktivität (neueste zuerst über id — kein start_time!)
        cursor = await db.execute(
            """SELECT name, activity_type, distance_km, duration_min, avg_hr, date
               FROM activities ORDER BY date DESC, id DESC LIMIT 1"""
        )
        last_act = await cursor.fetchone()

        # Nächstes Rennen
        cursor = await db.execute(
            """SELECT title, date_start FROM events
               WHERE event_type = 'race' AND date_start >= ?
               ORDER BY date_start ASC LIMIT 1""",
            (today_str,),
        )
        next_race = await cursor.fetchone()

    # PMC
    daily_tss = {r[0]: float(r[1]) for r in tss_rows}
    full_pmc = calculate_pmc(daily_tss, warmup_start, date.today())
    today_pmc = full_pmc[-1] if full_pmc else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    # Empfehlung
    health = {}
    if health_row:
        health = dict(zip(
            ["readiness_score", "sleep_score", "body_battery", "hrv_status", "stress_total", "vo2max"],
            health_row,
        ))
    recommendation = get_recommendation(
        tsb=today_pmc["tsb"],
        readiness=health.get("readiness_score"),
        body_battery=health.get("body_battery"),
        hrv_status=health.get("hrv_status"),
    )

    # Tage bis nächstes Rennen
    next_race_ctx = None
    if next_race:
        race_date = date.fromisoformat(next_race[1])
        days_to_race = (race_date - date.today()).days
        next_race_ctx = {
            "title": next_race[0],
            "date": next_race[1],
            "days": days_to_race,
        }

    last_activity = None
    if last_act:
        last_activity = dict(zip(
            ["name", "activity_type", "distance_km", "duration_min", "avg_hr", "date"],
            last_act,
        ))

    return templates.TemplateResponse(request, "dashboard.html", {
        "title": "Dashboard",
        "recommendation": recommendation,
        "today_pmc": today_pmc,
        "health": health,
        "last_activity": last_activity,
        "next_race": next_race_ctx,
    })


@router.get("/manual", response_class=HTMLResponse)
async def manual_page(request: Request):
    """Zeigt MFA-Eingabe falls nötig, sonst manuellen Collection-Trigger."""
    mfa_pending = getattr(request.app.state, "mfa_pending", False)
    mfa_error = getattr(request.app.state, "mfa_error", None)
    last_collection = getattr(request.app.state, "last_collection", None)
    last_analysis = getattr(request.app.state, "last_analysis", None)
    return templates.TemplateResponse(
        request,
        "manual.html",
        {
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

    return _redirect(request, "/manual")


@router.post("/garmin/collect")
async def trigger_collection(request: Request):
    """Startet manuelle Datensammlung sofort."""
    from src.scheduler import trigger_collection_now
    config = request.app.state.config
    trigger_collection_now(config)
    logger.info("Manuelle Datensammlung ausgelöst")
    return _redirect(request, "/manual")


@router.post("/analysis/trigger")
async def trigger_analysis(request: Request):
    """Startet manuell eine Analyse (SSE-fähig via /analysis/stream)."""
    if getattr(request.app.state, "analysis_running", False):
        logger.info("Analyse läuft bereits — zweiten Start ignoriert")
        return _redirect(request, "/manual")

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
            request.app.state.analysis_queue = None  # Queue nach Abschluss leeren

    asyncio.create_task(run_analysis_task())
    logger.info("Analyse-Task gestartet")
    return _redirect(request, "/manual")


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
        request,
        "settings.html",
        {"title": "Einstellungen", "settings": settings, "saved": saved},
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
    return _redirect(request, "/settings?saved=1")


# ── GARMIN STATUS ──────────────────────────────────────────────────────────

@router.get("/garmin/status")
async def garmin_status(request: Request):
    """Gibt aktuellen Garmin-Verbindungsstatus als JSON zurück."""
    from src.collector.garmin_client import DEFAULT_TOKEN_PATH
    from src.storage.database import get_db

    config = request.app.state.config

    # 1. Keine Credentials
    if not config.garmin_user or not config.garmin_password:
        return {
            "state": "no_credentials",
            "label": "Keine Zugangsdaten",
            "detail": "Garmin-Credentials nicht konfiguriert",
            "color": "gray",
        }

    token_exists = DEFAULT_TOKEN_PATH.exists()

    # Letzten Analyses-Eintrag lesen
    last_status = None
    last_error = None
    last_date = None
    async for db in get_db():
        cursor = await db.execute(
            "SELECT date, status, error_message FROM analyses ORDER BY date DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            last_date, last_status, last_error = row[0], row[1], row[2]

    # 2. Rate-limited (letzter Sync mit 429)
    if last_status == "error" and last_error and "429" in last_error:
        return {
            "state": "rate_limited",
            "label": "Rate-limited",
            "detail": "Garmin blockiert — bitte 2 Stunden warten",
            "color": "red",
        }

    # 3. Connected (Token + letzter Sync erfolgreich)
    if token_exists and last_status == "success":
        return {
            "state": "connected",
            "label": "Verbunden",
            "detail": f"Letzter Sync: {last_date}" if last_date else "Token vorhanden",
            "color": "green",
        }

    # 4. Token vorhanden, aber noch kein/fehlerhafter Sync
    if token_exists:
        return {
            "state": "token_only",
            "label": "Token vorhanden",
            "detail": "Noch kein erfolgreicher Sync",
            "color": "yellow",
        }

    # 5. Kein Token, Credentials vorhanden
    return {
        "state": "disconnected",
        "label": "Nicht verbunden",
        "detail": "Kein Token — Verbindung testen",
        "color": "orange",
    }


# ── EVENTS ────────────────────────────────────────────────────────────────

@router.get("/events", response_class=HTMLResponse)
async def events_list(request: Request):
    from src.storage.events_repo import EventsRepo
    events = await EventsRepo().list_all()
    return templates.TemplateResponse(
        request, "events.html",
        {"title": "Events", "events": events, "mode": "list"},
    )


@router.get("/events/new", response_class=HTMLResponse)
async def events_new_form(request: Request):
    return templates.TemplateResponse(
        request, "events.html",
        {"title": "Events", "events": [], "mode": "new", "event": {}},
    )


@router.post("/events/new")
async def events_create(
    request: Request,
    event_type: str = Form(...),
    date_start: str = Form(...),
    title: str = Form(...),
    date_end: str = Form(""),
    priority: str = Form(""),
    distance_km: str = Form(""),
    elevation_m: str = Form(""),
    goal: str = Form(""),
    training_possible: str = Form("1"),
):
    from src.storage.events_repo import EventsRepo
    await EventsRepo().create({
        "event_type": event_type,
        "date_start": date_start,
        "date_end": date_end or None,
        "title": title,
        "priority": priority or None,
        "distance_km": float(distance_km) if distance_km else None,
        "elevation_m": int(elevation_m) if elevation_m else None,
        "goal": goal or None,
        "training_possible": training_possible == "1",
    })
    return _redirect(request, "/events")


@router.get("/events/{event_id}/edit", response_class=HTMLResponse)
async def events_edit_form(request: Request, event_id: int):
    from src.storage.events_repo import EventsRepo
    event = await EventsRepo().get(event_id)
    if not event:
        return _redirect(request, "/events")
    return templates.TemplateResponse(
        request, "events.html",
        {"title": "Events", "events": [], "mode": "edit", "event": event},
    )


@router.post("/events/{event_id}/edit")
async def events_update(
    request: Request,
    event_id: int,
    event_type: str = Form(...),
    date_start: str = Form(...),
    title: str = Form(...),
    date_end: str = Form(""),
    priority: str = Form(""),
    distance_km: str = Form(""),
    elevation_m: str = Form(""),
    goal: str = Form(""),
    training_possible: str = Form("1"),
):
    from src.storage.events_repo import EventsRepo
    await EventsRepo().update(event_id, {
        "event_type": event_type,
        "date_start": date_start,
        "date_end": date_end or None,
        "title": title,
        "priority": priority or None,
        "distance_km": float(distance_km) if distance_km else None,
        "elevation_m": int(elevation_m) if elevation_m else None,
        "goal": goal or None,
        "training_possible": training_possible == "1",
    })
    return _redirect(request, "/events")


@router.post("/events/{event_id}/delete")
async def events_delete(request: Request, event_id: int):
    from src.storage.events_repo import EventsRepo
    await EventsRepo().delete(event_id)
    return _redirect(request, "/events")


@router.get("/trends", response_class=HTMLResponse)
async def trends_view(request: Request, days: int = 90):
    from datetime import date, timedelta
    from ..storage.database import get_db
    from ..analysis.pmc import calculate_pmc
    from ..analysis.recommendation import get_recommendation
    from ..analysis.svg_charts import line_chart, bar_chart, pmc_chart

    display_start = date.today() - timedelta(days=days)
    warmup_start = display_start - timedelta(days=42)
    # Wochenvolumen — mindestens 84 Tage (12 Wochen) laden, unabhängig von ?days
    volume_start = date.today() - timedelta(days=84)
    volume_cutoff = min(display_start, volume_start)
    today_str = date.today().isoformat()

    # TSS für PMC (mit training_load Fallback)
    async for db in get_db():
        cursor = await db.execute(
            """SELECT date, COALESCE(SUM(COALESCE(tss, training_load, 0)), 0)
               FROM activities WHERE date >= ? GROUP BY date""",
            (warmup_start.isoformat(),),
        )
        tss_rows = await cursor.fetchall()

        # Gesundheitsdaten (nur vorhandene Spalten!)
        cursor = await db.execute(
            """SELECT date, readiness_score, sleep_score, body_battery, hrv_status, stress_total
               FROM daily_data WHERE date >= ? ORDER BY date""",
            (display_start.isoformat(),),
        )
        health_rows = await cursor.fetchall()

        # Wochenvolumen (distance_km bereits in km)
        cursor = await db.execute(
            """SELECT date, distance_km FROM activities
               WHERE date >= ? AND activity_type = 'cycling'""",
            (volume_cutoff.isoformat(),),
        )
        activity_rows = await cursor.fetchall()

    # PMC berechnen
    daily_tss = {r[0]: float(r[1]) for r in tss_rows}
    full_pmc = calculate_pmc(daily_tss, warmup_start, date.today())
    pmc_series = [p for p in full_pmc if p["date"] >= display_start.isoformat()]
    today_pmc = pmc_series[-1] if pmc_series else {"ctl": 0.0, "atl": 0.0, "tsb": 0.0}

    # Heutige Empfehlung
    today_health_row = next(
        (dict(zip(["date", "readiness_score", "sleep_score", "body_battery", "hrv_status", "stress_total"], r))
         for r in health_rows if r[0] == today_str),
        {},
    )
    recommendation = get_recommendation(
        tsb=today_pmc["tsb"],
        readiness=today_health_row.get("readiness_score"),
        body_battery=today_health_row.get("body_battery"),
        hrv_status=today_health_row.get("hrv_status"),
    )

    # Chart-Daten aufbereiten
    health_labels = [r[0][5:] for r in health_rows]  # MM-DD
    readiness_values = [r[1] for r in health_rows]    # readiness_score
    sleep_values = [r[2] for r in health_rows]        # sleep_score
    battery_values = [r[3] for r in health_rows]      # body_battery
    stress_values = [r[5] for r in health_rows]       # stress_total

    svg_pmc = pmc_chart(pmc_series)
    svg_readiness = line_chart(health_labels,
        [{"label": "Readiness", "values": readiness_values, "color": "#2ecc71"}],
        title="Readiness Score")
    svg_sleep = line_chart(health_labels,
        [{"label": "Schlaf", "values": sleep_values, "color": "#3498db"}],
        title="Schlafqualität")
    svg_battery = line_chart(health_labels,
        [{"label": "Body Battery", "values": battery_values, "color": "#f39c12"}],
        title="Body Battery")
    svg_stress = line_chart(health_labels,
        [{"label": "Stress", "values": stress_values, "color": "#e74c3c"}],
        title="Stress")

    # Wochenvolumen (letzte 12 Wochen, distance_km direkt verwenden)
    week_km: dict[str, float] = {}
    for row in activity_rows:
        d = date.fromisoformat(row[0])
        iso_year, iso_week, _ = d.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        week_km[week_key] = week_km.get(week_key, 0.0) + (row[1] or 0.0)

    today = date.today()
    week_labels = []
    week_values = []
    for w in range(11, -1, -1):
        ref = today - timedelta(weeks=w)
        iso_year, iso_week, _ = ref.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        week_labels.append(f"KW{iso_week}")
        week_values.append(week_km.get(key, 0.0))

    svg_volume = bar_chart(week_labels, week_values, color="#3498db", title="Wochenvolumen (km)")

    return templates.TemplateResponse(request, "trends.html", {
        "title": "Trends",
        "days": days,
        "svg_pmc": svg_pmc,
        "svg_readiness": svg_readiness,
        "svg_sleep": svg_sleep,
        "svg_battery": svg_battery,
        "svg_stress": svg_stress,
        "svg_volume": svg_volume,
        "today_pmc": today_pmc,
        "recommendation": recommendation,
    })


# ── KALENDER ──────────────────────────────────────────────────────────────

@router.get("/calendar", response_class=HTMLResponse)
async def calendar_view(request: Request, year: int = 0, month: int = 0):
    import calendar as cal_mod
    from datetime import date
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month

    # Kalender-Matrix (6 Wochen × 7 Tage, 0 = leere Zelle)
    cal = cal_mod.monthcalendar(year, month)
    month_name = cal_mod.month_name[month]

    # Prev / Next Monat
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Aktivitäten des Monats laden
    prefix = f"{year}-{month:02d}"
    activities_by_day: dict[int, list] = {}
    readiness_by_day: dict[int, int] = {}

    from src.storage.database import get_db as _get_db
    async for db in _get_db():
        cursor = await db.execute(
            "SELECT date, activity_type, distance_km FROM activities WHERE date LIKE ?",
            (f"{prefix}%",),
        )
        for row in await cursor.fetchall():
            d = int(row[0].split("-")[2])
            activities_by_day.setdefault(d, []).append({"activity_type": row[1], "distance_km": row[2]})

        cursor = await db.execute(
            "SELECT date, readiness_score FROM daily_data WHERE date LIKE ? AND readiness_score IS NOT NULL",
            (f"{prefix}%",),
        )
        for row in await cursor.fetchall():
            d = int(row[0].split("-")[2])
            readiness_by_day[d] = row[1]

    # Events des Monats laden
    from src.storage.events_repo import EventsRepo
    events_list = await EventsRepo().list_for_month(year, month)
    events_by_day: dict[int, list] = {}
    for ev in events_list:
        d = int(ev["date_start"].split("-")[2])
        events_by_day.setdefault(d, []).append(ev)

    return templates.TemplateResponse(
        request, "calendar.html",
        {
            "title": "Kalender",
            "cal": cal,
            "month_name": month_name,
            "year": year,
            "month": month,
            "today": today,
            "prev_year": prev_year, "prev_month": prev_month,
            "next_year": next_year, "next_month": next_month,
            "activities_by_day": activities_by_day,
            "readiness_by_day": readiness_by_day,
            "events_by_day": events_by_day,
        },
    )

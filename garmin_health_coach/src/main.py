import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import load_config
from .scheduler import start_scheduler, stop_scheduler
from .storage.database import init_db
from .web.router import router as web_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    await init_db()
    start_scheduler(config)
    app.state.config = config
    logger.info("Garmin Health Coach gestartet")
    yield
    stop_scheduler()
    logger.info("Garmin Health Coach beendet")


app = FastAPI(
    title="Garmin Health Coach",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def ingress_middleware(request: Request, call_next):
    ingress_path = request.headers.get("X-Ingress-Path", "")
    request.scope["root_path"] = ingress_path
    return await call_next(request)


app.include_router(web_router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "1.0.0"})

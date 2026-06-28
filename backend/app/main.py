from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alert_worker import run_alert_worker
from app.config import settings
from app.database import init_db
from app.routers import events, fleet_ops, incidents, robots, scenarios

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    alert_task = asyncio.create_task(run_alert_worker())
    yield
    alert_task.cancel()
    try:
        await alert_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="SwarmMon API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(robots.router)
app.include_router(fleet_ops.router)
app.include_router(incidents.router)
app.include_router(scenarios.router)


@app.get("/")
def root() -> dict:
    return {
        "service": "SwarmMon API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "http://localhost:5173",
        "hint": "Open the dashboard URL for the UI; this server is the REST API only.",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

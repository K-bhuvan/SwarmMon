from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth import verify_ingest_api_key
from app.database import get_session
from app.health_rules import HealthRulesEngine, StateUpdater
from app.schemas import EventBatch

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("/batch")
def ingest_events(
    batch: EventBatch,
    session: Session = Depends(get_session),
    _: None = Depends(verify_ingest_api_key),
) -> dict:
    updater = StateUpdater(session)
    updater.apply_events(batch.events)
    health = HealthRulesEngine(session)
    opened = health.process_events(batch.events)
    return {
        "accepted": len(batch.events),
        "incidents_opened": len(opened),
    }

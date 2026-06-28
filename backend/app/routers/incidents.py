import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.incident_engine import IncidentEngine
from app.schemas import IncidentResponse, IncidentSeverity, IncidentTimelineEntry

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    scenario_run_id: str | None = None,
    robot_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[IncidentResponse]:
    engine = IncidentEngine(session)
    incidents = engine.list_incidents(scenario_run_id=scenario_run_id, robot_id=robot_id)
    return [
        IncidentResponse(
            incident_id=inc.incident_id,
            scenario_run_id=inc.scenario_run_id,
            robot_id=inc.robot_id,
            severity=IncidentSeverity(inc.severity),
            started_at=inc.started_at,
            ended_at=inc.ended_at,
            summary=inc.summary,
            events=[
                IncidentTimelineEntry(
                    timestamp=datetime.fromisoformat(e["timestamp"]),
                    event_type=e["event_type"],
                    message=e["message"],
                )
                for e in json.loads(inc.timeline_json)
            ],
        )
        for inc in incidents
    ]

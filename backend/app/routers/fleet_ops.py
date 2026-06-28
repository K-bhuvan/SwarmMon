from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.fleet_registry import (
    get_or_create_alert_settings,
    list_registered_robots,
)
from app.models import FleetAlertSettings, RegisteredRobot, ScenarioRun
from app.auth import verify_ingest_api_key
from app.fleet_ingest import process_fleet_ingest
from app.schemas import (
    FleetAlertSettingsResponse,
    FleetAlertSettingsUpdate,
    FleetIngestRequest,
    FleetIngestResponse,
    FleetOnboardRequest,
    RegisteredRobotCreate,
    RegisteredRobotResponse,
    ScenarioRunCreate,
    ScenarioRunResponse,
)

router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


def _settings_response(row: FleetAlertSettings) -> FleetAlertSettingsResponse:
    return FleetAlertSettingsResponse(
        scenario_run_id=row.scenario_run_id,
        notify_email=row.notify_email,
        offline_alert_minutes=row.offline_alert_minutes,
        alerts_enabled=row.alerts_enabled,
        resend_configured=bool(settings.resend_api_key),
    )


@router.get("/settings/{scenario_run_id}", response_model=FleetAlertSettingsResponse)
def get_fleet_alert_settings(
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> FleetAlertSettingsResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    row = get_or_create_alert_settings(session, scenario_run_id)
    return _settings_response(row)


@router.put("/settings/{scenario_run_id}", response_model=FleetAlertSettingsResponse)
def update_fleet_alert_settings(
    scenario_run_id: str,
    body: FleetAlertSettingsUpdate,
    session: Session = Depends(get_session),
) -> FleetAlertSettingsResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    row = get_or_create_alert_settings(session, scenario_run_id)
    if body.notify_email is not None:
        row.notify_email = body.notify_email.strip() or None
    if body.offline_alert_minutes is not None:
        row.offline_alert_minutes = max(1, body.offline_alert_minutes)
    if body.alerts_enabled is not None:
        row.alerts_enabled = body.alerts_enabled
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _settings_response(row)


@router.get(
    "/robots/{scenario_run_id}",
    response_model=list[RegisteredRobotResponse],
)
def list_fleet_robots(
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> list[RegisteredRobotResponse]:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    return list_registered_robots(session, scenario_run_id)


@router.post(
    "/robots/{scenario_run_id}",
    response_model=RegisteredRobotResponse,
    status_code=201,
)
def register_fleet_robot(
    scenario_run_id: str,
    body: RegisteredRobotCreate,
    session: Session = Depends(get_session),
) -> RegisteredRobotResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")

    robot_id = body.robot_id.strip()
    if not robot_id:
        raise HTTPException(status_code=400, detail="robot_id is required")

    existing = session.exec(
        select(RegisteredRobot).where(
            RegisteredRobot.scenario_run_id == scenario_run_id,
            RegisteredRobot.robot_id == robot_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Robot already registered")

    reg = RegisteredRobot(
        scenario_run_id=scenario_run_id,
        robot_id=robot_id,
        label=body.label.strip() if body.label else None,
    )
    session.add(reg)
    session.commit()
    session.refresh(reg)

    count = len(
        session.exec(
            select(RegisteredRobot).where(
                RegisteredRobot.scenario_run_id == scenario_run_id
            )
        ).all()
    )
    run.robot_count = count
    session.add(run)
    session.commit()

    rows = list_registered_robots(session, scenario_run_id)
    return next(r for r in rows if r.robot_id == robot_id)


@router.delete("/robots/{scenario_run_id}/{robot_id}", status_code=204)
def unregister_fleet_robot(
    scenario_run_id: str,
    robot_id: str,
    session: Session = Depends(get_session),
) -> None:
    reg = session.exec(
        select(RegisteredRobot).where(
            RegisteredRobot.scenario_run_id == scenario_run_id,
            RegisteredRobot.robot_id == robot_id,
        )
    ).first()
    if reg is None:
        raise HTTPException(status_code=404, detail="Robot not registered")
    session.delete(reg)
    session.commit()


@router.post("/ingest", response_model=FleetIngestResponse)
def ingest_fleet_snapshot(
    body: FleetIngestRequest,
    session: Session = Depends(get_session),
    _: None = Depends(verify_ingest_api_key),
) -> FleetIngestResponse:
    """Accept a fleet-wide status snapshot (schema v1). Auto-discovers robots."""
    return process_fleet_ingest(session, body)


@router.post("/onboard", response_model=ScenarioRunResponse)
def onboard_field_fleet(
    body: FleetOnboardRequest,
    session: Session = Depends(get_session),
) -> ScenarioRunResponse:
    """Create a running field fleet, alert settings, and register robots in one step."""
    from app.routers.scenarios import _create_run, _to_response

    existing = session.get(ScenarioRun, body.scenario_run_id)
    if existing:
        if existing.simulator != "field_fleet":
            raise HTTPException(status_code=409, detail="Scenario run already exists")
        existing.status = "running"
        existing.started_at = datetime.utcnow()
        existing.completed_at = None
        existing.scenario_name = body.scenario_name
        session.add(existing)
        run = existing
    else:
        run = _create_run(
            session,
            ScenarioRunCreate(
                scenario_run_id=body.scenario_run_id,
                scenario_name=body.scenario_name,
                simulator="field_fleet",
                robot_profile="field_drone_v1",
                environment_profile="farm",
                robot_count=len(body.robots),
            ),
        )
    settings_row = get_or_create_alert_settings(session, body.scenario_run_id)
    settings_row.notify_email = body.notify_email
    settings_row.offline_alert_minutes = max(1, body.offline_alert_minutes)
    settings_row.alerts_enabled = bool(body.notify_email)
    session.add(settings_row)

    for robot in body.robots:
        robot_id = robot.robot_id.strip()
        if not robot_id:
            continue
        session.add(
            RegisteredRobot(
                scenario_run_id=body.scenario_run_id,
                robot_id=robot_id,
                label=robot.label.strip() if robot.label else None,
            )
        )

    run.robot_count = len(body.robots)
    session.add(run)
    session.commit()
    session.refresh(run)
    return _to_response(run)

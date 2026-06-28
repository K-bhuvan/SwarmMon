from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import settings
from app.fleet_standard import FLEET_INGEST_SCHEMA_VERSION
from app.health_rules import HealthRulesEngine, StateUpdater
from app.models import RegisteredRobot, ScenarioRun
from app.schemas import (
    DiagnosticEvent,
    DiagnosticLevel,
    FleetIngestRequest,
    FleetIngestResponse,
    HeartbeatEvent,
    SwarmMonEvent,
)


def _battery_level(pct: float) -> DiagnosticLevel:
    if pct < 20:
        return DiagnosticLevel.WARN
    return DiagnosticLevel.OK


def snapshot_to_events(body: FleetIngestRequest) -> list[SwarmMonEvent]:
    """Convert a fleet status snapshot into SwarmMon events."""
    fleet_id = body.fleet_id
    ts = body.timestamp
    events: list[SwarmMonEvent] = []

    for robot in body.robots:
        robot_id = robot.robot_id.strip()
        if not robot_id:
            continue
        if robot.online:
            events.append(
                HeartbeatEvent(
                    robot_id=robot_id,
                    scenario_run_id=fleet_id,
                    timestamp=ts,
                )
            )
        if robot.battery_pct is not None:
            pct = max(0.0, min(100.0, robot.battery_pct))
            events.append(
                DiagnosticEvent(
                    robot_id=robot_id,
                    scenario_run_id=fleet_id,
                    timestamp=ts,
                    name="Battery",
                    level=_battery_level(pct),
                    message=f"{pct:.0f}%",
                )
            )
    return events


def ensure_robots_registered(
    session: Session,
    scenario_run_id: str,
    *,
    robot_ids: list[str],
    labels: dict[str, str | None],
) -> int:
    """Auto-register robots seen in fleet ingest. Returns count of newly registered."""
    if not settings.auto_register_field_robots:
        return 0

    run = session.get(ScenarioRun, scenario_run_id)
    if run is None or run.simulator != "field_fleet":
        return 0

    registered = 0
    for robot_id in robot_ids:
        existing = session.exec(
            select(RegisteredRobot).where(
                RegisteredRobot.scenario_run_id == scenario_run_id,
                RegisteredRobot.robot_id == robot_id,
            )
        ).first()
        if existing:
            label = labels.get(robot_id)
            if label and not existing.label:
                existing.label = label
                session.add(existing)
            continue
        session.add(
            RegisteredRobot(
                scenario_run_id=scenario_run_id,
                robot_id=robot_id,
                label=labels.get(robot_id),
            )
        )
        registered += 1

    if registered:
        count = len(
            session.exec(
                select(RegisteredRobot).where(
                    RegisteredRobot.scenario_run_id == scenario_run_id
                )
            ).all()
        )
        run.robot_count = count
        session.add(run)

    return registered


def process_fleet_ingest(
    session: Session, body: FleetIngestRequest
) -> FleetIngestResponse:
    if body.schema_version != FLEET_INGEST_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported schema_version (expected {FLEET_INGEST_SCHEMA_VERSION})",
        )

    fleet_id = body.fleet_id.strip()
    if not fleet_id:
        raise HTTPException(status_code=400, detail="fleet_id is required")

    run = session.get(ScenarioRun, fleet_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Fleet not found — run onboard first (POST /api/v1/fleet/onboard)",
        )

    robot_ids = [r.robot_id.strip() for r in body.robots if r.robot_id.strip()]
    labels = {
        r.robot_id.strip(): (r.label.strip() if r.label else None)
        for r in body.robots
        if r.robot_id.strip()
    }
    registered = ensure_robots_registered(
        session, fleet_id, robot_ids=robot_ids, labels=labels
    )
    session.commit()

    events = snapshot_to_events(body)
    if events:
        updater = StateUpdater(session)
        updater.apply_events(events)
        health = HealthRulesEngine(session)
        health.process_events(events)

    return FleetIngestResponse(
        accepted=len(events),
        robots_seen=len(robot_ids),
        registered=registered,
        fleet_id=fleet_id,
        timestamp=body.timestamp,
    )

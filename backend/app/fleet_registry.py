from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.config import settings
from app.fleet_live import live_max_age_seconds
from app.models import FleetAlertSettings, RegisteredRobot, RobotState
from app.schemas import RegisteredRobotResponse
from app.time_utils import is_older_than


def get_or_create_alert_settings(
    session: Session, scenario_run_id: str
) -> FleetAlertSettings:
    row = session.get(FleetAlertSettings, scenario_run_id)
    if row is None:
        row = FleetAlertSettings(scenario_run_id=scenario_run_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def compute_robot_status(
    last_heartbeat: datetime | None,
    *,
    ever_seen: bool,
    live_max_age_seconds: int | None = None,
) -> str:
    max_age = live_max_age_seconds if live_max_age_seconds is not None else settings.live_fleet_max_age_seconds
    if not ever_seen or last_heartbeat is None:
        return "pending"
    if is_older_than(last_heartbeat, max_age):
        return "offline"
    return "live"


def list_registered_robots(
    session: Session, scenario_run_id: str
) -> list[RegisteredRobotResponse]:
    from app.models import ScenarioRun

    run = session.get(ScenarioRun, scenario_run_id)
    max_age = live_max_age_seconds(run.simulator if run else None)
    registered = session.exec(
        select(RegisteredRobot)
        .where(RegisteredRobot.scenario_run_id == scenario_run_id)
        .order_by(RegisteredRobot.robot_id)
    ).all()

    results: list[RegisteredRobotResponse] = []
    for reg in registered:
        state = session.exec(
            select(RobotState).where(
                RobotState.scenario_run_id == scenario_run_id,
                RobotState.robot_id == reg.robot_id,
            )
        ).first()
        last_hb = state.last_heartbeat if state else None
        ever_seen = last_hb is not None
        status = compute_robot_status(last_hb, ever_seen=ever_seen, live_max_age_seconds=max_age)
        online = status == "live"
        results.append(
            RegisteredRobotResponse(
                robot_id=reg.robot_id,
                scenario_run_id=scenario_run_id,
                label=reg.label,
                registered_at=reg.registered_at,
                status=status,
                last_heartbeat=last_hb,
                online=online,
            )
        )
    return results

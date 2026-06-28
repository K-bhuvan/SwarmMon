from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.config import settings
from app.fleet_live import live_max_age_seconds
from app.health_rules import StateUpdater
from app.models import RegisteredRobot, ScenarioRun
from app.time_utils import is_older_than
from app.models import (
    ComponentState,
    DiagnosticState,
    RobotState,
    SignalState,
)
from app.schemas import (
    ComponentStateResponse,
    ComponentStatus,
    DiagnosticEvent,
    DiagnosticLevel,
    FleetResponse,
    RobotResponse,
    SignalStateResponse,
    SignalStatus,
)


def build_robot_response(
    session: Session,
    robot_id: str,
    scenario_run_id: str,
    *,
    live_timeout: bool = True,
    simulator: str | None = None,
) -> RobotResponse:
    state = session.exec(
        select(RobotState).where(
            RobotState.robot_id == robot_id,
            RobotState.scenario_run_id == scenario_run_id,
        )
    ).first()

    online = False
    last_heartbeat = None
    if state:
        online = state.online
        last_heartbeat = state.last_heartbeat
        if live_timeout and is_older_than(
            last_heartbeat, live_max_age_seconds(simulator)
        ):
            online = False

    signals = session.exec(
        select(SignalState).where(
            SignalState.robot_id == robot_id,
            SignalState.scenario_run_id == scenario_run_id,
        )
    ).all()
    components = session.exec(
        select(ComponentState).where(
            ComponentState.robot_id == robot_id,
            ComponentState.scenario_run_id == scenario_run_id,
        )
    ).all()
    diagnostics = session.exec(
        select(DiagnosticState).where(
            DiagnosticState.robot_id == robot_id,
            DiagnosticState.scenario_run_id == scenario_run_id,
        )
    ).all()

    return RobotResponse(
        robot_id=robot_id,
        scenario_run_id=scenario_run_id,
        online=online,
        last_heartbeat=last_heartbeat,
        signals=[
            SignalStateResponse(
                signal_id=s.signal_id,
                signal_type=s.signal_type,
                message_type=s.message_type,
                expected_rate_hz=s.expected_rate_hz,
                last_seen_ms_ago=s.last_seen_ms_ago,
                status=SignalStatus(s.status),
                last_updated=s.last_updated,
            )
            for s in signals
        ],
        components=[
            ComponentStateResponse(
                component_id=c.component_id,
                component_type=c.component_type,
                status=ComponentStatus(c.status),
                last_updated=c.last_updated,
            )
            for c in components
        ],
        diagnostics=[
            DiagnosticEvent(
                robot_id=robot_id,
                scenario_run_id=scenario_run_id,
                timestamp=d.timestamp,
                name=d.name,
                level=DiagnosticLevel(d.level),
                message=d.message,
            )
            for d in diagnostics
        ],
    )


def build_fleet_response(
    session: Session, scenario_run_id: str | None = None, *, live: bool = False
) -> FleetResponse:
    run = session.get(ScenarioRun, scenario_run_id) if scenario_run_id else None
    simulator = run.simulator if run else None
    max_age = live_max_age_seconds(simulator)

    live_timeout = True
    if scenario_run_id:
        if live:
            if run is None or run.status != "running":
                return FleetResponse(
                    scenario_run_id=scenario_run_id,
                    robots=[],
                    live_max_age_seconds=max_age,
                    simulator=simulator,
                )
        elif run and run.status == "completed":
            live_timeout = False
        updater = StateUpdater(session)
        if live_timeout:
            updater.refresh_offline_robots(scenario_run_id)
    else:
        updater = StateUpdater(session)
        updater.refresh_offline_robots(scenario_run_id)

    if scenario_run_id and simulator == "field_fleet":
        registered = session.exec(
            select(RegisteredRobot)
            .where(RegisteredRobot.scenario_run_id == scenario_run_id)
            .order_by(RegisteredRobot.robot_id)
        ).all()
        robot_ids = [r.robot_id for r in registered]
        if not robot_ids:
            states = session.exec(
                select(RobotState).where(RobotState.scenario_run_id == scenario_run_id)
            ).all()
            robot_ids = sorted({s.robot_id for s in states})
    else:
        stmt = select(RobotState)
        if scenario_run_id:
            stmt = stmt.where(RobotState.scenario_run_id == scenario_run_id)
        robot_ids = sorted({r.robot_id for r in session.exec(stmt).all()})

    robot_responses = [
        build_robot_response(
            session,
            robot_id,
            scenario_run_id or "",
            live_timeout=live_timeout,
            simulator=simulator,
        )
        for robot_id in robot_ids
    ]

    if live and simulator != "field_fleet":
        robot_responses = [
            r
            for r in robot_responses
            if r.last_heartbeat is not None
            and not is_older_than(r.last_heartbeat, max_age)
        ]

    return FleetResponse(
        scenario_run_id=scenario_run_id,
        robots=robot_responses,
        live_max_age_seconds=max_age,
        simulator=simulator,
    )

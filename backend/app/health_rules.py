from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, select

from app.config import settings
from app.incident_engine import IncidentEngine
from app.time_utils import ensure_utc, is_older_than, utc_now
from app.models import (
    ComponentState,
    DiagnosticState,
    Incident,
    RobotState,
    ScenarioRun,
    SignalState,
    StoredEvent,
)
from app.schemas import (
    ComponentStateEvent,
    ComponentStatus,
    DiagnosticEvent,
    DiagnosticLevel,
    FaultInjectedEvent,
    HeartbeatEvent,
    IncidentSeverity,
    SignalFreshnessEvent,
    SignalStatus,
    SwarmMonEvent,
)


def _as_db_time(value: datetime) -> datetime:
    """Store UTC as naive datetime for consistent SQLite round-trips."""
    return ensure_utc(value).replace(tzinfo=None)


class StateUpdater:
    """Apply incoming events to persisted robot/signal/component state."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def apply_events(self, events: list[SwarmMonEvent]) -> None:
        for scenario_run_id in {e.scenario_run_id for e in events}:
            self._reactivate_live_run(scenario_run_id)
        for event in events:
            self._store_event(event)
            self._touch_robot(event.robot_id, event.scenario_run_id)
            if isinstance(event, HeartbeatEvent):
                self._apply_heartbeat(event)
            elif isinstance(event, ComponentStateEvent):
                self._apply_component(event)
            elif isinstance(event, SignalFreshnessEvent):
                self._apply_signal(event)
            elif isinstance(event, DiagnosticEvent):
                self._apply_diagnostic(event)
        self.session.commit()

    def _reactivate_live_run(self, scenario_run_id: str) -> None:
        """Resume a live simulator run if telemetry arrives after a premature auto-complete."""
        run = self.session.get(ScenarioRun, scenario_run_id)
        if run is None or run.status != "completed":
            return
        if run.simulator == "replay":
            return
        run.status = "running"
        run.started_at = _as_db_time(utc_now())
        run.completed_at = None
        self.session.add(run)

    def _store_event(self, event: SwarmMonEvent) -> None:
        self.session.add(
            StoredEvent(
                event_type=event.event_type,
                robot_id=event.robot_id,
                scenario_run_id=event.scenario_run_id,
                timestamp=event.timestamp,
                payload_json=event.model_dump_json(),
            )
        )

    def _get_robot_state(self, robot_id: str, scenario_run_id: str) -> RobotState:
        stmt = select(RobotState).where(
            RobotState.robot_id == robot_id,
            RobotState.scenario_run_id == scenario_run_id,
        )
        state = self.session.exec(stmt).first()
        if state is None:
            state = RobotState(robot_id=robot_id, scenario_run_id=scenario_run_id)
            self.session.add(state)
            self.session.flush()
        return state

    def _touch_robot(self, robot_id: str, scenario_run_id: str) -> None:
        self._get_robot_state(robot_id, scenario_run_id)

    def _apply_heartbeat(self, event: HeartbeatEvent) -> None:
        state = self._get_robot_state(event.robot_id, event.scenario_run_id)
        state.last_heartbeat = _as_db_time(event.timestamp)
        state.online = True
        state.updated_at = _as_db_time(utc_now())

    def _apply_component(self, event: ComponentStateEvent) -> None:
        stmt = select(ComponentState).where(
            ComponentState.robot_id == event.robot_id,
            ComponentState.scenario_run_id == event.scenario_run_id,
            ComponentState.component_id == event.component_id,
        )
        row = self.session.exec(stmt).first()
        if row is None:
            row = ComponentState(
                robot_id=event.robot_id,
                scenario_run_id=event.scenario_run_id,
                component_id=event.component_id,
                component_type=event.component_type,
                status=event.status.value,
                last_updated=event.timestamp,
            )
            self.session.add(row)
        else:
            row.component_type = event.component_type
            row.status = event.status.value
            row.last_updated = event.timestamp

    def _apply_signal(self, event: SignalFreshnessEvent) -> None:
        stmt = select(SignalState).where(
            SignalState.robot_id == event.robot_id,
            SignalState.scenario_run_id == event.scenario_run_id,
            SignalState.signal_id == event.signal_id,
        )
        row = self.session.exec(stmt).first()
        if row is None:
            row = SignalState(
                robot_id=event.robot_id,
                scenario_run_id=event.scenario_run_id,
                signal_id=event.signal_id,
                signal_type=event.signal_type,
                message_type=event.message_type,
                expected_rate_hz=event.expected_rate_hz,
                last_seen_ms_ago=event.last_seen_ms_ago,
                status=event.status.value,
                last_updated=event.timestamp,
            )
            self.session.add(row)
        else:
            row.signal_type = event.signal_type
            row.message_type = event.message_type
            row.expected_rate_hz = event.expected_rate_hz
            row.last_seen_ms_ago = event.last_seen_ms_ago
            row.status = event.status.value
            row.last_updated = event.timestamp

    def _apply_diagnostic(self, event: DiagnosticEvent) -> None:
        stmt = select(DiagnosticState).where(
            DiagnosticState.robot_id == event.robot_id,
            DiagnosticState.scenario_run_id == event.scenario_run_id,
            DiagnosticState.name == event.name,
        )
        row = self.session.exec(stmt).first()
        if row is None:
            row = DiagnosticState(
                robot_id=event.robot_id,
                scenario_run_id=event.scenario_run_id,
                name=event.name,
                level=event.level.value,
                message=event.message,
                timestamp=event.timestamp,
            )
            self.session.add(row)
        else:
            row.level = event.level.value
            row.message = event.message
            row.timestamp = event.timestamp

    def refresh_offline_robots(self, scenario_run_id: str | None = None) -> None:
        stmt = select(RobotState)
        if scenario_run_id:
            stmt = stmt.where(RobotState.scenario_run_id == scenario_run_id)
        for robot in self.session.exec(stmt):
            if is_older_than(robot.last_heartbeat, settings.heartbeat_timeout_seconds):
                robot.online = False
                robot.updated_at = _as_db_time(utc_now())
        self.session.commit()


class HealthRulesEngine:
    """Evaluate health rules and open/close incidents from event streams."""

    DIAGNOSTIC_LEVEL_ORDER = {
        DiagnosticLevel.OK: 0,
        DiagnosticLevel.WARN: 1,
        DiagnosticLevel.ERROR: 2,
        DiagnosticLevel.STALE: 1,
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.incident_engine = IncidentEngine(session)

    def process_events(self, events: list[SwarmMonEvent]) -> list[Incident]:
        opened: list[Incident] = []
        for event in events:
            if isinstance(event, SignalFreshnessEvent) and event.status == SignalStatus.STALE:
                inc = self.incident_engine.open_or_update(
                    scenario_run_id=event.scenario_run_id,
                    robot_id=event.robot_id,
                    severity=IncidentSeverity.WARN,
                    summary=f"Signal freshness degraded for {event.signal_id}",
                    entry_timestamp=event.timestamp,
                    entry_type="SIGNAL_STALE",
                    entry_message=f"{event.signal_id} exceeded freshness threshold",
                    incident_key=f"signal_stale:{event.signal_id}",
                )
                if inc:
                    opened.append(inc)
            elif isinstance(event, SignalFreshnessEvent) and event.status == SignalStatus.OK:
                self.incident_engine.try_close(
                    scenario_run_id=event.scenario_run_id,
                    robot_id=event.robot_id,
                    incident_key=f"signal_stale:{event.signal_id}",
                    entry_timestamp=event.timestamp,
                    entry_type="SIGNAL_RECOVERED",
                    entry_message=f"{event.signal_id} recovered",
                )
            elif isinstance(event, ComponentStateEvent) and event.status != ComponentStatus.OK:
                inc = self.incident_engine.open_or_update(
                    scenario_run_id=event.scenario_run_id,
                    robot_id=event.robot_id,
                    severity=IncidentSeverity.ERROR,
                    summary=f"Component unhealthy: {event.component_id}",
                    entry_timestamp=event.timestamp,
                    entry_type="COMPONENT_UNHEALTHY",
                    entry_message=f"{event.component_id} status {event.status.value}",
                    incident_key=f"component:{event.component_id}",
                )
                if inc:
                    opened.append(inc)
            elif isinstance(event, DiagnosticEvent) and self.DIAGNOSTIC_LEVEL_ORDER.get(
                event.level, 0
            ) >= self.DIAGNOSTIC_LEVEL_ORDER[DiagnosticLevel.WARN]:
                severity = (
                    IncidentSeverity.ERROR
                    if event.level == DiagnosticLevel.ERROR
                    else IncidentSeverity.WARN
                )
                inc = self.incident_engine.open_or_update(
                    scenario_run_id=event.scenario_run_id,
                    robot_id=event.robot_id,
                    severity=severity,
                    summary=f"Diagnostic {event.level.value}: {event.name}",
                    entry_timestamp=event.timestamp,
                    entry_type="DIAGNOSTIC",
                    entry_message=event.message,
                    incident_key=f"diagnostic:{event.name}",
                )
                if inc:
                    opened.append(inc)
            elif isinstance(event, FaultInjectedEvent):
                self.incident_engine.add_timeline_note(
                    scenario_run_id=event.scenario_run_id,
                    robot_id=event.robot_id,
                    entry_timestamp=event.timestamp,
                    entry_type="FAULT_INJECTED",
                    entry_message=event.message,
                )
        self.session.commit()
        return opened

    def check_offline_robots(self, scenario_run_id: str) -> list[Incident]:
        """Open incidents for robots that missed heartbeat within timeout."""
        opened: list[Incident] = []
        stmt = select(RobotState).where(RobotState.scenario_run_id == scenario_run_id)
        for robot in self.session.exec(stmt):
            if is_older_than(robot.last_heartbeat, settings.heartbeat_timeout_seconds):
                if robot.online:
                    robot.online = False
                    inc = self.incident_engine.open_or_update(
                        scenario_run_id=scenario_run_id,
                        robot_id=robot.robot_id,
                        severity=IncidentSeverity.ERROR,
                        summary=f"Robot offline: {robot.robot_id}",
                        entry_timestamp=utc_now(),
                        entry_type="ROBOT_OFFLINE",
                        entry_message="No heartbeat within configured timeout",
                        incident_key="robot_offline",
                    )
                    if inc:
                        opened.append(inc)
        self.session.commit()
        return opened

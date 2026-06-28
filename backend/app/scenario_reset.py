from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, delete, select

from app.models import (
    ComponentState,
    DiagnosticState,
    Incident,
    RobotState,
    ScenarioRun,
    SignalState,
    StoredEvent,
)


def reset_scenario_run_data(session: Session, scenario_run_id: str) -> dict[str, int]:
    """Clear ingested state for a scenario run (keeps the scenario run record)."""
    counts: dict[str, int] = {}
    for model, key in (
        (StoredEvent, "events"),
        (RobotState, "robot_states"),
        (SignalState, "signal_states"),
        (ComponentState, "component_states"),
        (DiagnosticState, "diagnostic_states"),
        (Incident, "incidents"),
    ):
        stmt = delete(model).where(model.scenario_run_id == scenario_run_id)  # type: ignore[attr-defined]
        result = session.exec(stmt)
        counts[key] = result.rowcount or 0

    run = session.get(ScenarioRun, scenario_run_id)
    if run:
        run.status = "running"
        run.started_at = datetime.utcnow()
        run.completed_at = None
        run.replay_artifact_path = None
        session.add(run)

    session.commit()
    return counts

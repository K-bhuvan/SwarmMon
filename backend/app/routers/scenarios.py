import json
from datetime import datetime
from pathlib import Path

import yaml

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.health_rules import HealthRulesEngine
from app.models import RobotState, ScenarioRun
from app.scenario_loader import (
    load_scenario_file,
    resolve_scenario_path,
    scenario_yaml_to_run_create,
)
from app.scenario_report_engine import ScenarioReportEngine
from app.scenario_reset import reset_scenario_run_data
from app.time_utils import is_older_than
from app.schemas import (
    ScenarioReportResponse,
    ScenarioRunComplete,
    ScenarioRunCreate,
    ScenarioRunFromYaml,
    ScenarioRunResponse,
)

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


def _finalize_stale_running_scenarios(session: Session) -> None:
    """Mark abandoned live runs completed so the dashboard never shows ghost streams."""
    stale_after = max(settings.live_fleet_max_age_seconds * 3, 30)
    runs = session.exec(select(ScenarioRun).where(ScenarioRun.status == "running")).all()
    changed = False
    for run in runs:
        if run.simulator in ("replay", "field_fleet"):
            continue
        robots = session.exec(
            select(RobotState).where(RobotState.scenario_run_id == run.scenario_run_id)
        ).all()
        if not robots:
            # Grace period after reset/start before the first heartbeat lands.
            if is_older_than(run.started_at, stale_after):
                run.status = "completed"
                run.completed_at = datetime.utcnow()
                session.add(run)
                changed = True
            continue
        heartbeats = [r.last_heartbeat for r in robots if r.last_heartbeat is not None]
        if not heartbeats:
            continue
        newest = max(heartbeats)
        if is_older_than(newest, stale_after):
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            session.add(run)
            changed = True
    if changed:
        session.commit()


def _create_run(session: Session, body: ScenarioRunCreate) -> ScenarioRun:
    run = ScenarioRun(
        scenario_run_id=body.scenario_run_id,
        scenario_name=body.scenario_name,
        simulator=body.simulator,
        robot_profile=body.robot_profile,
        environment_profile=body.environment_profile,
        robot_count=body.robot_count,
        config_json=json.dumps(body.config) if body.config else None,
        status="running",
        started_at=datetime.utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


@router.get("/runs", response_model=list[ScenarioRunResponse])
def list_scenario_runs(session: Session = Depends(get_session)) -> list[ScenarioRunResponse]:
    _finalize_stale_running_scenarios(session)
    runs = session.exec(select(ScenarioRun).order_by(ScenarioRun.started_at.desc())).all()
    return [_to_response(run) for run in runs]


@router.get("/runs/{scenario_run_id}", response_model=ScenarioRunResponse)
def get_scenario_run(
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> ScenarioRunResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    return _to_response(run)


@router.post("/runs", response_model=ScenarioRunResponse)
def create_scenario_run(
    body: ScenarioRunCreate,
    session: Session = Depends(get_session),
) -> ScenarioRunResponse:
    existing = session.get(ScenarioRun, body.scenario_run_id)
    if existing:
        raise HTTPException(status_code=409, detail="Scenario run already exists")
    return _to_response(_create_run(session, body))


@router.post("/runs/from-yaml", response_model=ScenarioRunResponse)
def create_scenario_run_from_yaml(
    body: ScenarioRunFromYaml,
    session: Session = Depends(get_session),
) -> ScenarioRunResponse:
    existing = session.get(ScenarioRun, body.scenario_run_id)
    if existing:
        raise HTTPException(status_code=409, detail="Scenario run already exists")

    scenarios_dir = Path(settings.scenarios_dir)
    try:
        path = resolve_scenario_path(scenarios_dir, body.scenario_name)
        yaml_data = load_scenario_file(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (yaml.YAMLError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid scenario YAML: {exc}") from exc

    run_create = scenario_yaml_to_run_create(yaml_data, body.scenario_run_id)
    return _to_response(_create_run(session, run_create))


@router.post("/runs/{scenario_run_id}/reset")
def reset_scenario_run(
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> dict:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    cleared = reset_scenario_run_data(session, scenario_run_id)
    return {"scenario_run_id": scenario_run_id, "cleared": cleared}


@router.post("/runs/{scenario_run_id}/complete", response_model=ScenarioRunResponse)
def complete_scenario_run(
    scenario_run_id: str,
    body: ScenarioRunComplete,
    session: Session = Depends(get_session),
) -> ScenarioRunResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    if body.replay_artifact_path:
        run.replay_artifact_path = body.replay_artifact_path
    session.add(run)
    session.commit()
    session.refresh(run)

    # Snapshot final online flags at completion time for completed runs.
    health = HealthRulesEngine(session)
    health.check_offline_robots(scenario_run_id)
    return _to_response(run)


@router.get("/runs/{scenario_run_id}/report", response_model=ScenarioReportResponse)
def get_scenario_report(
    scenario_run_id: str,
    session: Session = Depends(get_session),
) -> ScenarioReportResponse:
    run = session.get(ScenarioRun, scenario_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    engine = ScenarioReportEngine(session)
    return engine.generate_report(scenario_run_id)


def _to_response(run: ScenarioRun) -> ScenarioRunResponse:
    return ScenarioRunResponse(
        scenario_run_id=run.scenario_run_id,
        scenario_name=run.scenario_name,
        simulator=run.simulator,
        robot_profile=run.robot_profile,
        environment_profile=run.environment_profile,
        robot_count=run.robot_count,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        replay_artifact_path=run.replay_artifact_path,
    )

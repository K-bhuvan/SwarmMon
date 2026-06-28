from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.database import get_session
from app.fleet_summary import robot_health, summarize_robots
from app.health_rules import HealthRulesEngine
from app.incident_engine import IncidentEngine
from app.main import app
from app.scenario_loader import load_scenario_file, scenario_yaml_to_run_create
from app.scenario_report_engine import ScenarioReportEngine
from app.schemas import (
    ComponentStateResponse,
    ComponentStatus,
    DiagnosticEvent,
    DiagnosticLevel,
    IncidentSeverity,
    RobotResponse,
    SignalFreshnessEvent,
    SignalStateResponse,
    SignalStatus,
)

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
def client():
    SQLModel.metadata.create_all(TEST_ENGINE)

    def override_get_session():
        with Session(TEST_ENGINE) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(TEST_ENGINE)


@pytest.fixture
def session(client):
    with Session(TEST_ENGINE) as s:
        yield s


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_event_batch_and_fleet(client):
    ts = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    events = {
        "events": [
            {
                "event_type": "heartbeat",
                "robot_id": "robot-01",
                "scenario_run_id": "run-001",
                "timestamp": ts,
            },
            {
                "event_type": "signal_freshness",
                "robot_id": "robot-01",
                "scenario_run_id": "run-001",
                "timestamp": ts,
                "signal_id": "/scan",
                "signal_type": "ros2_topic",
                "message_type": "sensor_msgs/msg/LaserScan",
                "expected_rate_hz": 10,
                "last_seen_ms_ago": 100,
                "status": "OK",
            },
        ]
    }
    r = client.post("/api/v1/events/batch", json=events)
    assert r.status_code == 200
    assert r.json()["accepted"] == 2

    fleet = client.get("/api/v1/fleet", params={"scenario_run_id": "run-001"})
    assert fleet.status_code == 200
    data = fleet.json()
    assert len(data["robots"]) == 1
    assert data["robots"][0]["robot_id"] == "robot-01"


def test_fault_injected_timeline(client):
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-fault",
            "scenario_name": "fault_test",
            "simulator": "replay",
            "robot_count": 1,
        },
    )
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "fault_injected",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-fault",
                    "timestamp": "2026-06-23T12:22:00Z",
                    "fault_type": "sensor_rate_drop",
                    "signal_id": "/scan",
                    "message": "fault injected: sensor_rate_drop on /scan",
                },
                {
                    "event_type": "signal_freshness",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-fault",
                    "timestamp": "2026-06-23T12:22:04Z",
                    "signal_id": "/scan",
                    "signal_type": "ros2_topic",
                    "last_seen_ms_ago": 900,
                    "status": "STALE",
                },
            ]
        },
    )
    incidents = client.get("/api/v1/incidents", params={"scenario_run_id": "run-fault"})
    assert incidents.status_code == 200
    items = incidents.json()
    assert len(items) >= 1
    timeline_types = [e["event_type"] for e in items[0]["events"]]
    assert "FAULT_INJECTED" in timeline_types or any(
        "SIGNAL_STALE" in t for t in timeline_types
    )


def test_completed_scenario_snapshot_keeps_online(client):
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-snap",
            "scenario_name": "snapshot_test",
            "simulator": "replay",
            "robot_count": 1,
        },
    )
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "heartbeat",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-snap",
                    "timestamp": ts,
                }
            ]
        },
    )
    client.post("/api/v1/scenarios/runs/run-snap/complete", json={})
    fleet = client.get("/api/v1/fleet", params={"scenario_run_id": "run-snap"})
    assert fleet.json()["robots"][0]["online"] is True

    live_fleet = client.get(
        "/api/v1/fleet",
        params={"scenario_run_id": "run-snap", "live": True},
    )
    assert live_fleet.status_code == 200
    assert live_fleet.json()["robots"] == []


def test_live_fleet_hides_stale_running_robots(client):
    old_ts = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-stale",
            "scenario_name": "stale_test",
            "simulator": "ros2_harness",
            "robot_count": 1,
        },
    )
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "heartbeat",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-stale",
                    "timestamp": old_ts,
                }
            ]
        },
    )
    snapshot = client.get(
        "/api/v1/fleet", params={"scenario_run_id": "run-stale"}
    ).json()
    assert len(snapshot["robots"]) == 1

    live = client.get(
        "/api/v1/fleet", params={"scenario_run_id": "run-stale", "live": True}
    ).json()
    assert live["robots"] == []


def test_reset_refreshes_started_at(client):
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-reset",
            "scenario_name": "reset_test",
            "simulator": "ros2_harness",
            "robot_count": 1,
        },
    )
    runs = client.get("/api/v1/scenarios/runs").json()
    run = next(r for r in runs if r["scenario_run_id"] == "run-reset")
    original_started = run["started_at"]

    client.post("/api/v1/scenarios/runs/run-reset/reset")
    runs = client.get("/api/v1/scenarios/runs").json()
    run = next(r for r in runs if r["scenario_run_id"] == "run-reset")
    assert run["status"] == "running"
    assert run["started_at"] >= original_started


def test_live_run_reactivates_on_telemetry_after_auto_complete(client):
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-reactivate",
            "scenario_name": "reactivate_test",
            "simulator": "ros2_harness",
            "robot_count": 1,
        },
    )
    client.post("/api/v1/scenarios/runs/run-reactivate/complete", json={})
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "heartbeat",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-reactivate",
                    "timestamp": ts,
                }
            ]
        },
    )
    run = client.get("/api/v1/scenarios/runs/run-reactivate").json()
    assert run["status"] == "running"
    assert run["completed_at"] is None
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "heartbeat",
                    "robot_id": "robot-01",
                    "scenario_run_id": "run-001",
                    "timestamp": ts,
                },
                {
                    "event_type": "heartbeat",
                    "robot_id": "robot-02",
                    "scenario_run_id": "run-001",
                    "timestamp": ts,
                },
                {
                    "event_type": "signal_freshness",
                    "robot_id": "robot-02",
                    "scenario_run_id": "run-001",
                    "timestamp": ts,
                    "signal_id": "/scan",
                    "signal_type": "ros2_topic",
                    "last_seen_ms_ago": 900,
                    "status": "STALE",
                },
            ]
        },
    )
    summary = client.get("/api/v1/fleet/summary", params={"scenario_run_id": "run-001"})
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 2
    assert body["warn"] >= 1


def test_stale_signal_opens_incident(client):
    ts = "2026-06-23T12:22:04Z"
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "signal_freshness",
                    "robot_id": "robot-05",
                    "scenario_run_id": "run-001",
                    "timestamp": ts,
                    "signal_id": "/scan",
                    "signal_type": "ros2_topic",
                    "last_seen_ms_ago": 900,
                    "status": "STALE",
                }
            ]
        },
    )
    incidents = client.get("/api/v1/incidents", params={"scenario_run_id": "run-001"})
    assert incidents.status_code == 200
    assert len(incidents.json()) >= 1


def test_scenario_run_from_yaml(client):
    r = client.post(
        "/api/v1/scenarios/runs/from-yaml",
        json={
            "scenario_run_id": "run-yaml-001",
            "scenario_name": "warehouse_amr_observability_test",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scenario_name"] == "warehouse_amr_observability_test"
    assert body["robot_count"] == 5
    assert body["simulator"] == "isaac_sim"

    listed = client.get("/api/v1/scenarios/runs")
    assert listed.status_code == 200
    assert any(row["scenario_run_id"] == "run-yaml-001" for row in listed.json())


def test_scenario_run_and_report(client):
    client.post(
        "/api/v1/scenarios/runs",
        json={
            "scenario_run_id": "run-001",
            "scenario_name": "warehouse_amr_observability_test",
            "simulator": "replay",
            "robot_profile": "generic_amr_v1",
            "environment_profile": "warehouse_small",
            "robot_count": 5,
            "config": {
                "expected_outcomes": {
                    "required_signals": ["/scan"],
                    "incidents_required": True,
                }
            },
        },
    )
    client.post(
        "/api/v1/events/batch",
        json={
            "events": [
                {
                    "event_type": "signal_freshness",
                    "robot_id": "robot-05",
                    "scenario_run_id": "run-001",
                    "timestamp": "2026-06-23T12:22:04Z",
                    "signal_id": "/scan",
                    "signal_type": "ros2_topic",
                    "last_seen_ms_ago": 900,
                    "status": "STALE",
                }
            ]
        },
    )
    client.post(
        "/api/v1/scenarios/runs/run-001/complete",
        json={"replay_artifact_path": "backend/tests/fixtures/sample_events.jsonl"},
    )
    report = client.get("/api/v1/scenarios/runs/run-001/report")
    assert report.status_code == 200
    assert report.json()["total_incidents"] >= 1


def test_incident_open_close(session):
    engine = IncidentEngine(session)
    started = datetime(2026, 6, 23, 12, 22, 4, tzinfo=timezone.utc)
    opened = engine.open_or_update(
        scenario_run_id="run-001",
        robot_id="robot-05",
        severity=IncidentSeverity.WARN,
        summary="Signal freshness degraded for /scan",
        entry_timestamp=started,
        entry_type="SIGNAL_STALE",
        entry_message="/scan exceeded freshness threshold",
        incident_key="signal_stale:/scan",
    )
    assert opened is not None
    session.commit()

    closed = engine.try_close(
        scenario_run_id="run-001",
        robot_id="robot-05",
        incident_key="signal_stale:/scan",
        entry_timestamp=started.replace(second=21),
        entry_type="SIGNAL_RECOVERED",
        entry_message="/scan recovered",
    )
    assert closed is not None
    assert closed.open is False


def test_health_rules_stale_opens_incident(session):
    health = HealthRulesEngine(session)
    ts = datetime(2026, 6, 23, 12, 22, 4, tzinfo=timezone.utc)
    opened = health.process_events(
        [
            SignalFreshnessEvent(
                robot_id="robot-05",
                scenario_run_id="run-001",
                timestamp=ts,
                signal_id="/scan",
                signal_type="ros2_topic",
                last_seen_ms_ago=900,
                status=SignalStatus.STALE,
            )
        ]
    )
    assert len(opened) == 1


def test_fleet_summary_helpers():
    ok_robot = RobotResponse(
        robot_id="robot-01",
        scenario_run_id="run-001",
        online=True,
        last_heartbeat=datetime.now(timezone.utc),
        signals=[
            SignalStateResponse(
                signal_id="/scan",
                signal_type="ros2_topic",
                message_type=None,
                expected_rate_hz=10,
                last_seen_ms_ago=50,
                status=SignalStatus.OK,
                last_updated=None,
            )
        ],
    )
    warn_robot = RobotResponse(
        robot_id="robot-02",
        scenario_run_id="run-001",
        online=True,
        last_heartbeat=datetime.now(timezone.utc),
        signals=[
            SignalStateResponse(
                signal_id="/scan",
                signal_type="ros2_topic",
                message_type=None,
                expected_rate_hz=10,
                last_seen_ms_ago=900,
                status=SignalStatus.STALE,
                last_updated=None,
            )
        ],
    )
    assert robot_health(ok_robot) == "ok"
    assert robot_health(warn_robot) == "warn"
    summary = summarize_robots([ok_robot, warn_robot])
    assert summary["ok"] == 1
    assert summary["warn"] == 1


def test_scenario_yaml_loader():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "simulation" / "scenarios" / "warehouse_amr_observability_test.yaml"
    data = load_scenario_file(path)
    run = scenario_yaml_to_run_create(data, "run-test")
    assert run.scenario_name == "warehouse_amr_observability_test"
    assert run.robot_count == 5
    assert "/diagnostics" in run.config["expected_outcomes"]["required_signals"]


def test_scenario_report_requires_run(session, client):
    report = client.get("/api/v1/scenarios/runs/missing/report")
    assert report.status_code == 404

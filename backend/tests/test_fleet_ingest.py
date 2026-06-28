from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401
from app.database import get_session
from app.main import app

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


def _onboard(client: TestClient, fleet_id: str = "mike-farm") -> None:
    r = client.post(
        "/api/v1/fleet/onboard",
        json={
            "scenario_run_id": fleet_id,
            "scenario_name": "Test field fleet",
            "robots": [],
        },
    )
    assert r.status_code == 200


def test_onboard_reactivates_completed_field_fleet(client):
    _onboard(client)
    complete = client.post("/api/v1/scenarios/runs/mike-farm/complete", json={})
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    again = client.post(
        "/api/v1/fleet/onboard",
        json={
            "scenario_run_id": "mike-farm",
            "scenario_name": "Test field fleet",
            "robots": [],
        },
    )
    assert again.status_code == 200
    assert again.json()["status"] == "running"


def test_field_fleet_live_returns_all_robots(client):
    _onboard(client)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.post(
        "/api/v1/fleet/ingest",
        json={
            "schema_version": 1,
            "fleet_id": "mike-farm",
            "timestamp": ts,
            "robots": [
                {"robot_id": "drone-01", "online": True, "battery_pct": 80},
                {"robot_id": "drone-02", "online": True, "battery_pct": 70},
            ],
        },
    )
    live = client.get(
        "/api/v1/fleet",
        params={"scenario_run_id": "mike-farm", "live": True},
    ).json()
    assert live["simulator"] == "field_fleet"
    assert live["live_max_age_seconds"] == 45
    assert len(live["robots"]) == 2
    assert all(r["online"] for r in live["robots"])


def test_fleet_ingest_auto_registers_robots(client):
    _onboard(client)
    ts = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    payload = {
        "schema_version": 1,
        "fleet_id": "mike-farm",
        "timestamp": ts,
        "robots": [
            {"robot_id": "drone-01", "label": "North", "online": True, "battery_pct": 82},
            {"robot_id": "drone-02", "online": True, "battery_pct": 55},
            {"robot_id": "drone-03", "online": False, "battery_pct": 10},
        ],
    }
    r = client.post("/api/v1/fleet/ingest", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["robots_seen"] == 3
    assert body["registered"] == 3
    assert body["accepted"] == 5  # 2 heartbeats + 3 battery diagnostics

    roster = client.get("/api/v1/fleet/robots/mike-farm").json()
    assert len(roster) == 3
    ids = {row["robot_id"] for row in roster}
    assert ids == {"drone-01", "drone-02", "drone-03"}


def test_fleet_ingest_unknown_fleet_404(client):
    ts = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    r = client.post(
        "/api/v1/fleet/ingest",
        json={
            "schema_version": 1,
            "fleet_id": "missing-fleet",
            "timestamp": ts,
            "robots": [{"robot_id": "drone-01", "online": True}],
        },
    )
    assert r.status_code == 404


def test_fleet_ingest_scales_without_manual_register(client):
    _onboard(client)
    ts = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    robots = [
        {"robot_id": f"drone-{i:02d}", "online": True, "battery_pct": 70}
        for i in range(1, 21)
    ]
    r = client.post(
        "/api/v1/fleet/ingest",
        json={
            "schema_version": 1,
            "fleet_id": "mike-farm",
            "timestamp": ts,
            "robots": robots,
        },
    )
    assert r.status_code == 200
    assert r.json()["registered"] == 20
    roster = client.get("/api/v1/fleet/robots/mike-farm").json()
    assert len(roster) == 20

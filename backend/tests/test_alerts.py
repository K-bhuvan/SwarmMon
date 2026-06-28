from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.alert_service import process_fleet_alerts
from app.database import get_session
from app.main import app
from app.models import (
    FleetAlertSettings,
    RegisteredRobot,
    RobotState,
    ScenarioRun,
)

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
def session():
    SQLModel.metadata.create_all(TEST_ENGINE)

    def override_get_session():
        with Session(TEST_ENGINE) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app):
        with Session(TEST_ENGINE) as s:
            yield s
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(TEST_ENGINE)


def _seed_fleet(session: Session) -> None:
    session.add(
        ScenarioRun(
            scenario_run_id="mike-farm",
            scenario_name="Test farm",
            simulator="field_fleet",
            robot_count=1,
            status="running",
        )
    )
    session.add(
        FleetAlertSettings(
            scenario_run_id="mike-farm",
            notify_email="mike@example.com",
            offline_alert_minutes=5,
            alerts_enabled=True,
        )
    )
    session.add(
        RegisteredRobot(
            scenario_run_id="mike-farm",
            robot_id="drone-01",
            label="North",
        )
    )
    old = datetime(2020, 1, 1, 12, 0, 0)
    session.add(
        RobotState(
            robot_id="drone-01",
            scenario_run_id="mike-farm",
            online=True,
            last_heartbeat=old,
        )
    )
    session.commit()


@patch("app.alert_service.send_email")
@patch("app.config.settings.resend_api_key", "re_test")
def test_offline_alert_sent_once(mock_send, session: Session):
    _seed_fleet(session)
    sent = process_fleet_alerts(session)
    assert sent == 1
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "mike@example.com"

    sent_again = process_fleet_alerts(session)
    assert sent_again == 0
    assert mock_send.call_count == 1


@patch("app.alert_service.send_email")
@patch("app.config.settings.resend_api_key", "re_test")
def test_offline_alerts_batched_into_one_email(mock_send, session: Session):
    _seed_fleet(session)
    old = datetime(2020, 1, 1, 12, 0, 0)
    for robot_id, label in [
        ("drone-02", "South field"),
        ("drone-03", "East field"),
        ("drone-04", "West field"),
    ]:
        session.add(
            RegisteredRobot(
                scenario_run_id="mike-farm",
                robot_id=robot_id,
                label=label,
            )
        )
        session.add(
            RobotState(
                robot_id=robot_id,
                scenario_run_id="mike-farm",
                online=True,
                last_heartbeat=old,
            )
        )
    session.commit()

    sent = process_fleet_alerts(session)
    assert sent == 1
    mock_send.assert_called_once()
    subject = mock_send.call_args.kwargs["subject"]
    body = mock_send.call_args.kwargs["html"]
    assert "4 drones offline" in subject
    assert "drone-01" in body
    assert "drone-04" in body
    assert "South field" in body


@patch("app.alert_service.send_email")
@patch("app.config.settings.resend_api_key", "re_test")
def test_recovery_alert_after_heartbeat(mock_send, session: Session):
    _seed_fleet(session)
    process_fleet_alerts(session)

    state = session.exec(
        select(RobotState).where(RobotState.robot_id == "drone-01")
    ).first()
    assert state is not None
    state.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(state)
    session.commit()

    sent = process_fleet_alerts(session)
    assert sent == 1
    assert mock_send.call_count == 2
    subjects = [c.kwargs["subject"] for c in mock_send.call_args_list]
    assert any("offline" in s.lower() for s in subjects)
    assert any("back online" in s.lower() for s in subjects)

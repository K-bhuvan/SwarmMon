from datetime import datetime

from sqlmodel import Field, SQLModel


class ScenarioRun(SQLModel, table=True):
    __tablename__ = "scenario_runs"

    scenario_run_id: str = Field(primary_key=True)
    scenario_name: str
    simulator: str = "replay"
    robot_profile: str | None = None
    environment_profile: str | None = None
    robot_count: int = 1
    status: str = "running"
    config_json: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    replay_artifact_path: str | None = None


class StoredEvent(SQLModel, table=True):
    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str
    robot_id: str
    scenario_run_id: str
    timestamp: datetime
    payload_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RobotState(SQLModel, table=True):
    __tablename__ = "robot_states"

    id: int | None = Field(default=None, primary_key=True)
    robot_id: str = Field(index=True)
    scenario_run_id: str = Field(index=True)
    online: bool = True
    last_heartbeat: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SignalState(SQLModel, table=True):
    __tablename__ = "signal_states"

    id: int | None = Field(default=None, primary_key=True)
    robot_id: str = Field(index=True)
    scenario_run_id: str = Field(index=True)
    signal_id: str = Field(index=True)
    signal_type: str
    message_type: str | None = None
    expected_rate_hz: float | None = None
    last_seen_ms_ago: int | None = None
    status: str
    last_updated: datetime | None = None


class ComponentState(SQLModel, table=True):
    __tablename__ = "component_states"

    id: int | None = Field(default=None, primary_key=True)
    robot_id: str = Field(index=True)
    scenario_run_id: str = Field(index=True)
    component_id: str = Field(index=True)
    component_type: str
    status: str
    last_updated: datetime | None = None


class DiagnosticState(SQLModel, table=True):
    __tablename__ = "diagnostic_states"

    id: int | None = Field(default=None, primary_key=True)
    robot_id: str = Field(index=True)
    scenario_run_id: str = Field(index=True)
    name: str = Field(index=True)
    level: str
    message: str
    timestamp: datetime


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    incident_id: str = Field(primary_key=True)
    scenario_run_id: str = Field(index=True)
    robot_id: str = Field(index=True)
    severity: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str
    timeline_json: str
    open: bool = True


class RegisteredRobot(SQLModel, table=True):
    """Robots expected in a fleet — shown as pending until first heartbeat."""

    __tablename__ = "registered_robots"

    id: int | None = Field(default=None, primary_key=True)
    scenario_run_id: str = Field(index=True)
    robot_id: str = Field(index=True)
    label: str | None = None
    registered_at: datetime = Field(default_factory=datetime.utcnow)


class FleetAlertSettings(SQLModel, table=True):
    __tablename__ = "fleet_alert_settings"

    scenario_run_id: str = Field(primary_key=True)
    notify_email: str | None = None
    offline_alert_minutes: int = 5
    alerts_enabled: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AlertNotificationState(SQLModel, table=True):
    """Tracks sent offline/recovery emails to avoid spam."""

    __tablename__ = "alert_notification_states"

    id: int | None = Field(default=None, primary_key=True)
    scenario_run_id: str = Field(index=True)
    robot_id: str = Field(index=True)
    offline_alert_sent: bool = False
    last_offline_email_at: datetime | None = None
    last_recovery_email_at: datetime | None = None

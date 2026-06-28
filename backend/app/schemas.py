from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class ComponentStatus(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    UNHEALTHY = "UNHEALTHY"


class SignalStatus(str, Enum):
    OK = "OK"
    STALE = "STALE"
    MISSING = "MISSING"


class DiagnosticLevel(str, Enum):
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"
    STALE = "STALE"


class HeartbeatEvent(BaseModel):
    event_type: Literal["heartbeat"] = "heartbeat"
    robot_id: str
    scenario_run_id: str
    timestamp: datetime


class ComponentStateEvent(BaseModel):
    event_type: Literal["component_state"] = "component_state"
    robot_id: str
    scenario_run_id: str
    timestamp: datetime
    component_id: str
    component_type: str
    status: ComponentStatus


class SignalFreshnessEvent(BaseModel):
    event_type: Literal["signal_freshness"] = "signal_freshness"
    robot_id: str
    scenario_run_id: str
    timestamp: datetime
    signal_id: str
    signal_type: str
    message_type: str | None = None
    expected_rate_hz: float | None = None
    last_seen_ms_ago: int
    status: SignalStatus


class DiagnosticEvent(BaseModel):
    event_type: Literal["diagnostic"] = "diagnostic"
    robot_id: str
    scenario_run_id: str
    timestamp: datetime
    name: str
    level: DiagnosticLevel
    message: str


class FaultInjectedEvent(BaseModel):
    event_type: Literal["fault_injected"] = "fault_injected"
    robot_id: str
    scenario_run_id: str
    timestamp: datetime
    fault_type: str
    signal_id: str | None = None
    message: str


SwarmMonEvent = Annotated[
    Union[
        HeartbeatEvent,
        ComponentStateEvent,
        SignalFreshnessEvent,
        DiagnosticEvent,
        FaultInjectedEvent,
    ],
    Field(discriminator="event_type"),
]


class EventBatch(BaseModel):
    events: list[SwarmMonEvent]


class IncidentTimelineEntry(BaseModel):
    timestamp: datetime
    event_type: str
    message: str


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class IncidentResponse(BaseModel):
    incident_id: str
    scenario_run_id: str
    robot_id: str
    severity: IncidentSeverity
    started_at: datetime
    ended_at: datetime | None = None
    summary: str
    events: list[IncidentTimelineEntry]


class SignalStateResponse(BaseModel):
    signal_id: str
    signal_type: str
    message_type: str | None = None
    expected_rate_hz: float | None = None
    last_seen_ms_ago: int | None = None
    status: SignalStatus
    last_updated: datetime | None = None


class ComponentStateResponse(BaseModel):
    component_id: str
    component_type: str
    status: ComponentStatus
    last_updated: datetime | None = None


class RobotResponse(BaseModel):
    robot_id: str
    scenario_run_id: str | None = None
    online: bool
    last_heartbeat: datetime | None = None
    signals: list[SignalStateResponse] = Field(default_factory=list)
    components: list[ComponentStateResponse] = Field(default_factory=list)
    diagnostics: list[DiagnosticEvent] = Field(default_factory=list)


class FleetResponse(BaseModel):
    robots: list[RobotResponse]
    scenario_run_id: str | None = None
    live_max_age_seconds: int = 10
    simulator: str | None = None


class FleetSummaryResponse(BaseModel):
    scenario_run_id: str | None = None
    total: int
    online: int
    ok: int
    warn: int
    error: int
    offline: int
    unknown: int
    stale_signals: int


class ScenarioRunCreate(BaseModel):
    scenario_run_id: str
    scenario_name: str
    simulator: str = "replay"
    robot_profile: str | None = None
    environment_profile: str | None = None
    robot_count: int = 1
    config: dict | None = None


class ScenarioRunResponse(BaseModel):
    scenario_run_id: str
    scenario_name: str
    simulator: str
    robot_profile: str | None = None
    environment_profile: str | None = None
    robot_count: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    replay_artifact_path: str | None = None


class ScenarioRunComplete(BaseModel):
    replay_artifact_path: str | None = None


class ScenarioRunFromYaml(BaseModel):
    scenario_run_id: str
    scenario_name: str = "warehouse_amr_observability_test"


class ScenarioReportResponse(BaseModel):
    scenario_run_id: str
    scenario_name: str
    simulator: str
    robot_profile: str | None = None
    environment_profile: str | None = None
    robot_count: int
    total_incidents: int
    incident_severity_breakdown: dict[str, int]
    detection_latency_seconds: list[float]
    missed_expected_failures: int
    false_offline_count: int
    missing_required_signals: list[str]
    replay_artifact_path: str | None = None
    scenario_passed: bool
    summary: str


class FleetAlertSettingsResponse(BaseModel):
    scenario_run_id: str
    notify_email: str | None = None
    offline_alert_minutes: int
    alerts_enabled: bool
    resend_configured: bool


class FleetAlertSettingsUpdate(BaseModel):
    notify_email: str | None = None
    offline_alert_minutes: int | None = None
    alerts_enabled: bool | None = None


class RegisteredRobotCreate(BaseModel):
    robot_id: str
    label: str | None = None


class RegisteredRobotResponse(BaseModel):
    robot_id: str
    scenario_run_id: str
    label: str | None = None
    registered_at: datetime
    status: str
    last_heartbeat: datetime | None = None
    online: bool = False


class FleetOnboardRequest(BaseModel):
    scenario_run_id: str
    scenario_name: str = "Field fleet"
    notify_email: str | None = None
    offline_alert_minutes: int = 5
    robots: list[RegisteredRobotCreate] = Field(default_factory=list)


class FleetStatusRobotIngest(BaseModel):
    robot_id: str
    label: str | None = None
    online: bool = True
    battery_pct: float | None = None


class FleetIngestRequest(BaseModel):
    schema_version: int = 1
    fleet_id: str
    timestamp: datetime
    robots: list[FleetStatusRobotIngest] = Field(default_factory=list)


class FleetIngestResponse(BaseModel):
    accepted: int
    robots_seen: int
    registered: int
    fleet_id: str
    timestamp: datetime

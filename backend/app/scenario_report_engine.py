from __future__ import annotations

import json
from datetime import datetime

import yaml
from sqlmodel import Session, select

from app.config import settings
from app.incident_engine import IncidentEngine
from app.models import Incident, ScenarioRun, SignalState
from app.schemas import ScenarioReportResponse, SignalStatus


class ScenarioReportEngine:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.incident_engine = IncidentEngine(session)

    def generate_report(self, scenario_run_id: str) -> ScenarioReportResponse:
        run = self.session.get(ScenarioRun, scenario_run_id)
        if run is None:
            raise ValueError(f"Scenario run not found: {scenario_run_id}")

        incidents = self.incident_engine.list_incidents(scenario_run_id=scenario_run_id)
        severity_breakdown: dict[str, int] = {}
        detection_latencies: list[float] = []

        config = self._load_config(run.config_json)
        expected_outcomes = config.get("expected_outcomes", {}) if config else {}
        required_signals = expected_outcomes.get("required_signals", [])
        max_detection_latency = expected_outcomes.get("max_detection_latency_seconds", 10)
        max_false_offline = expected_outcomes.get("max_false_offline_count", 0)
        incidents_required = expected_outcomes.get("incidents_required", False)

        for inc in incidents:
            severity_breakdown[inc.severity] = severity_breakdown.get(inc.severity, 0) + 1
            latency = self._detection_latency(inc)
            if latency is not None:
                detection_latencies.append(latency)

        missing_signals = self._missing_required_signals(scenario_run_id, required_signals)
        false_offline_count = sum(
            1
            for inc in incidents
            if inc.summary.startswith("Robot offline") and not self._fault_matches_robot(config, inc)
        )

        missed_failures = 0
        if incidents_required and len(incidents) == 0:
            missed_failures += 1
        if any(lat > max_detection_latency for lat in detection_latencies):
            missed_failures += 1

        scenario_passed = (
            missed_failures == 0
            and false_offline_count <= max_false_offline
            and len(missing_signals) == 0
        )

        summary = (
            "Robot setup can be observed well enough before hardware deployment."
            if scenario_passed
            else "Scenario did not meet expected observability outcomes."
        )

        return ScenarioReportResponse(
            scenario_run_id=run.scenario_run_id,
            scenario_name=run.scenario_name,
            simulator=run.simulator,
            robot_profile=run.robot_profile,
            environment_profile=run.environment_profile,
            robot_count=run.robot_count,
            total_incidents=len(incidents),
            incident_severity_breakdown=severity_breakdown,
            detection_latency_seconds=detection_latencies,
            missed_expected_failures=missed_failures,
            false_offline_count=false_offline_count,
            missing_required_signals=missing_signals,
            replay_artifact_path=run.replay_artifact_path,
            scenario_passed=scenario_passed,
            summary=summary,
        )

    @staticmethod
    def _load_config(config_json: str | None) -> dict:
        if not config_json:
            return {}
        try:
            return json.loads(config_json)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _detection_latency(incident: Incident) -> float | None:
        timeline = json.loads(incident.timeline_json)
        fault_time: datetime | None = None
        detect_time: datetime | None = None
        for entry in timeline:
            ts = datetime.fromisoformat(entry["timestamp"])
            if entry["event_type"] == "FAULT_INJECTED":
                fault_time = ts
            if entry["event_type"] in ("SIGNAL_STALE", "ROBOT_OFFLINE", "COMPONENT_UNHEALTHY"):
                detect_time = ts
        if fault_time and detect_time:
            return (detect_time - fault_time).total_seconds()
        return None

    def _missing_required_signals(
        self, scenario_run_id: str, required_signals: list[str]
    ) -> list[str]:
        if not required_signals:
            return []
        missing: list[str] = []
        for signal_id in required_signals:
            stmt = select(SignalState).where(
                SignalState.scenario_run_id == scenario_run_id,
                SignalState.signal_id == signal_id,
            )
            row = self.session.exec(stmt).first()
            if row is None or row.status == SignalStatus.MISSING.value:
                missing.append(signal_id)
        return missing

    @staticmethod
    def _fault_matches_robot(config: dict, incident: Incident) -> bool:
        faults = config.get("faults", []) if config else []
        for fault in faults:
            affected = fault.get("affected_robots", [])
            if incident.robot_id in affected:
                return True
        return False

    @staticmethod
    def load_scenario_yaml(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

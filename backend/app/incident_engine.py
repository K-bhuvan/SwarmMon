from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlmodel import Session, select

from app.models import Incident
from app.schemas import IncidentSeverity


class IncidentEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _load_timeline(self, incident: Incident) -> list[dict]:
        return json.loads(incident.timeline_json)

    def _save_timeline(self, incident: Incident, timeline: list[dict]) -> None:
        incident.timeline_json = json.dumps(timeline)

    @staticmethod
    def _stable_incident_id(scenario_run_id: str, robot_id: str, incident_key: str) -> str:
        slug = incident_key.replace("/", "_").replace(":", "_")
        return f"inc-{scenario_run_id}-{robot_id}-{slug}"[:120]

    def open_or_update(
        self,
        scenario_run_id: str,
        robot_id: str,
        severity: IncidentSeverity,
        summary: str,
        entry_timestamp: datetime,
        entry_type: str,
        entry_message: str,
        incident_key: str,
    ) -> Incident | None:
        incident_id = self._stable_incident_id(scenario_run_id, robot_id, incident_key)
        incident = self.session.get(Incident, incident_id)
        entry = {
            "timestamp": entry_timestamp.isoformat(),
            "event_type": entry_type,
            "message": entry_message,
        }
        if incident is None:
            incident = Incident(
                incident_id=incident_id,
                scenario_run_id=scenario_run_id,
                robot_id=robot_id,
                severity=severity.value,
                started_at=entry_timestamp,
                summary=summary,
                timeline_json=json.dumps([entry]),
                open=True,
            )
            self.session.add(incident)
            self.session.flush()
            return incident
        if not incident.open:
            return None
        timeline = self._load_timeline(incident)
        if timeline[-1]["event_type"] != entry_type or timeline[-1]["message"] != entry_message:
            timeline.append(entry)
            self._save_timeline(incident, timeline)
        return None

    def try_close(
        self,
        scenario_run_id: str,
        robot_id: str,
        incident_key: str,
        entry_timestamp: datetime,
        entry_type: str,
        entry_message: str,
    ) -> Incident | None:
        incident_id = self._stable_incident_id(scenario_run_id, robot_id, incident_key)
        incident = self.session.get(Incident, incident_id)
        if incident is None or not incident.open:
            return None
        timeline = self._load_timeline(incident)
        timeline.append(
            {
                "timestamp": entry_timestamp.isoformat(),
                "event_type": entry_type,
                "message": entry_message,
            }
        )
        incident.ended_at = entry_timestamp
        incident.open = False
        self._save_timeline(incident, timeline)
        return incident

    def add_timeline_note(
        self,
        scenario_run_id: str,
        robot_id: str,
        entry_timestamp: datetime,
        entry_type: str,
        entry_message: str,
    ) -> None:
        stmt = select(Incident).where(
            Incident.scenario_run_id == scenario_run_id,
            Incident.robot_id == robot_id,
            Incident.open == True,  # noqa: E712
        )
        incidents = list(self.session.exec(stmt))
        entry = {
            "timestamp": entry_timestamp.isoformat(),
            "event_type": entry_type,
            "message": entry_message,
        }
        if incidents:
            for incident in incidents:
                timeline = self._load_timeline(incident)
                timeline.append(entry)
                self._save_timeline(incident, timeline)
        else:
            incident_id = f"inc-{uuid.uuid4().hex[:8]}"
            self.session.add(
                Incident(
                    incident_id=incident_id,
                    scenario_run_id=scenario_run_id,
                    robot_id=robot_id,
                    severity=IncidentSeverity.INFO.value,
                    started_at=entry_timestamp,
                    ended_at=entry_timestamp,
                    summary=entry_message,
                    timeline_json=json.dumps([entry]),
                    open=False,
                )
            )

    def list_incidents(
        self, scenario_run_id: str | None = None, robot_id: str | None = None
    ) -> list[Incident]:
        stmt = select(Incident)
        if scenario_run_id:
            stmt = stmt.where(Incident.scenario_run_id == scenario_run_id)
        if robot_id:
            stmt = stmt.where(Incident.robot_id == robot_id)
        stmt = stmt.order_by(Incident.started_at)
        return list(self.session.exec(stmt))

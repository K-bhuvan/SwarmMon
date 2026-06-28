from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from swarmmon_agent.config import AgentSettings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BackendClient:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.base = settings.backend_url.rstrip("/")

    def ensure_scenario_run(self) -> None:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base}/api/v1/scenarios/runs/from-yaml",
                json={
                    "scenario_run_id": self.settings.scenario_run_id,
                    "scenario_name": self.settings.scenario_name,
                },
            )
            if resp.status_code == 409:
                client.post(
                    f"{self.base}/api/v1/scenarios/runs/{self.settings.scenario_run_id}/reset"
                ).raise_for_status()
            elif resp.status_code >= 400:
                # Fallback for older backends or missing YAML
                client.post(
                    f"{self.base}/api/v1/scenarios/runs",
                    json={
                        "scenario_run_id": self.settings.scenario_run_id,
                        "scenario_name": self.settings.scenario_name,
                        "simulator": "ros2_harness",
                        "robot_count": 1,
                    },
                )

    def send_batch(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base}/api/v1/events/batch",
                json={"events": events},
            )
            resp.raise_for_status()

    def complete_run(self) -> None:
        with httpx.Client(timeout=30.0) as client:
            payload: dict[str, Any] = {}
            if self.settings.jsonl_path:
                payload["replay_artifact_path"] = self.settings.jsonl_path
            resp = client.post(
                f"{self.base}/api/v1/scenarios/runs/{self.settings.scenario_run_id}/complete",
                json=payload,
            )
            resp.raise_for_status()


class JsonlWriter:
    def __init__(self, path: str | None) -> None:
        self.path = Path(path) if path else None
        self._file = None

    def __enter__(self) -> JsonlWriter:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(self, *args: object) -> None:
        if self._file:
            self._file.close()

    def write(self, event: dict[str, Any]) -> None:
        if self._file:
            self._file.write(json.dumps(event, default=str) + "\n")
            self._file.flush()

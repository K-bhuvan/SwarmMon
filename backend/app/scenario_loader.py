from __future__ import annotations

from pathlib import Path

import yaml

from app.schemas import ScenarioRunCreate


def load_scenario_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Scenario YAML must be a mapping")
    return data


def scenario_yaml_to_run_create(yaml_data: dict, scenario_run_id: str) -> ScenarioRunCreate:
    scenario = yaml_data.get("scenario", {})
    fleet = yaml_data.get("fleet", {})
    environment = yaml_data.get("environment", {})

    signals = yaml_data.get("signals", {})
    required_signals = [sid for sid, cfg in signals.items() if cfg.get("required")]

    expected = dict(yaml_data.get("expected_outcomes", {}))
    if required_signals and "required_signals" not in expected:
        expected["required_signals"] = required_signals

    config = dict(yaml_data)
    if expected:
        config["expected_outcomes"] = expected

    return ScenarioRunCreate(
        scenario_run_id=scenario_run_id,
        scenario_name=scenario.get("name", scenario_run_id),
        simulator=scenario.get("simulator", "replay"),
        robot_profile=fleet.get("robot_profile"),
        environment_profile=environment.get("profile"),
        robot_count=int(fleet.get("robot_count", 1)),
        config=config,
    )


def resolve_scenario_path(scenarios_dir: Path, scenario_name: str) -> Path:
    """Resolve scenario name or path to a YAML file under scenarios_dir."""
    candidate = Path(scenario_name)
    if candidate.suffix in {".yaml", ".yml"}:
        if candidate.is_file():
            return candidate
        nested = scenarios_dir / candidate.name
        if nested.is_file():
            return nested
    else:
        for name in (f"{scenario_name}.yaml", f"{scenario_name}.yml"):
            path = scenarios_dir / name
            if path.is_file():
                return path
    raise FileNotFoundError(f"Scenario not found: {scenario_name}")

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWARMMON_")

    backend_url: str = "http://localhost:8000"
    robot_id: str = "robot-01"
    scenario_run_id: str = "run-ros2-live"
    scenario_name: str = "ros2_live_test"
    poll_interval_seconds: float = 2.0
    batch_size: int = 50
    jsonl_path: str | None = None

    # Signal expectations (from robot profile)
    scan_topic: str = "/scan"
    odom_topic: str = "/odom"
    diagnostics_topic: str = "/diagnostics"
    scan_expected_hz: float = 10.0
    odom_expected_hz: float = 30.0
    scan_stale_ms: int = 500
    odom_stale_ms: int = 200

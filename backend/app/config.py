from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_SCENARIOS_DIR = _REPO_ROOT / "simulation" / "scenarios"
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SWARMMON_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./swarmmon.db"
    heartbeat_timeout_seconds: int = 30
    live_fleet_max_age_seconds: int = 10
    # Field fleets publish ~every 30s on ROS — use a wider live window than ros2_live.
    field_fleet_live_max_age_seconds: int = 45
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    scenarios_dir: str = str(_DEFAULT_SCENARIOS_DIR)

    # Email alerts (Resend — free tier: https://resend.com)
    resend_api_key: str | None = None
    resend_from_email: str = "SwarmMon <onboarding@resend.dev>"
    alert_poll_seconds: int = 60

    # Optional ingest protection for field agents
    ingest_api_key: str | None = None

    # Auto-register robots from fleet ingest snapshots (field_fleet only)
    auto_register_field_robots: bool = True


settings = Settings()

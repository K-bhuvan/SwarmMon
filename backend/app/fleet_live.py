from app.config import settings


def live_max_age_seconds(simulator: str | None) -> int:
    """How long a heartbeat stays 'live' on the dashboard for this simulator type."""
    if simulator == "field_fleet":
        return settings.field_fleet_live_max_age_seconds
    return settings.live_fleet_max_age_seconds

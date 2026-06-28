from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import settings


def verify_ingest_api_key(
    x_swarmmon_key: str | None = Header(default=None, alias="X-SwarmMon-Key"),
) -> None:
    expected = settings.ingest_api_key
    if not expected:
        return
    if x_swarmmon_key != expected:
        raise HTTPException(status_code=401, detail="Invalid ingest API key")

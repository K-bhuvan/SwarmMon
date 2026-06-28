from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

from app.alert_service import process_fleet_alerts
from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)


async def run_alert_worker() -> None:
    """Background loop — checks fleet offline state and sends Resend emails."""
    logger.info(
        "Alert worker started (poll=%ss, resend=%s)",
        settings.alert_poll_seconds,
        "configured" if settings.resend_api_key else "disabled",
    )
    while True:
        await asyncio.sleep(settings.alert_poll_seconds)
        if not settings.resend_api_key:
            continue
        try:
            with Session(engine) as session:
                sent = process_fleet_alerts(session)
                if sent:
                    logger.info("Sent %s alert email(s)", sent)
        except Exception:
            logger.exception("Alert worker tick failed")

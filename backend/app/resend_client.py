from __future__ import annotations

import httpx

from app.config import settings


class ResendError(Exception):
    pass


def send_email(*, to: str, subject: str, html: str) -> None:
    if not settings.resend_api_key:
        raise ResendError("SWARMMON_RESEND_API_KEY is not configured")
    if not to.strip():
        raise ResendError("Recipient email is empty")

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [to.strip()],
                "subject": subject,
                "html": html,
            },
        )
        if resp.status_code >= 400:
            raise ResendError(f"Resend API error {resp.status_code}: {resp.text}")

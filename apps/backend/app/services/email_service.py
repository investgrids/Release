"""
Outbound transactional email — currently just the returning-user feedback
notification (see app/api/feedback.py). Uses the Hostinger Mail API (bearer
token, REST) rather than plain SMTP — this backend's support@marketripple.in
mailbox is Hostinger-hosted and Hostinger issues a proper scoped API token
for it (see https://api.mail.hostinger.com), which is simpler and more
reliable here than the smtplib/STARTTLS path this replaced (no SMTP
host/port branching, no thread-pool wrapping for a sync library — the API
is a single async POST).

The API token never reaches the frontend — this module is backend-only, and
the request that triggers an email always returns success/failure based on
whether the DB write succeeded, not whether the email sent (see callers). A
missing/misconfigured token just logs a warning and no-ops rather than
raising, so email delivery is best-effort, not a hard dependency for the
feature it supports.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

_API_BASE = "https://api.mail.hostinger.com/api/v1"


async def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.hostinger_mail_api_token or not settings.hostinger_mailbox_resource_id:
        log.warning("email.not_configured", subject=subject)
        return False
    url = f"{_API_BASE}/mailboxes/{settings.hostinger_mailbox_resource_id}/send"
    headers = {"Authorization": f"Bearer {settings.hostinger_mail_api_token}"}
    payload = {"to": [to], "subject": subject, "text": body}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
        # 204 No Content on success per the API's own spec — anything else
        # (401 bad/rotated token, 422 malformed payload, 5xx upstream) is a
        # real failure, logged with the response body for diagnosis.
        if resp.status_code == 204:
            return True
        log.warning("email.send_failed", status=resp.status_code, body=resp.text[:300], subject=subject)
        return False
    except Exception as exc:
        log.warning("email.send_failed", error=str(exc), subject=subject)
        return False

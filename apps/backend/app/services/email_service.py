"""
Outbound transactional email — currently just the returning-user feedback
notification (see app/api/feedback.py). Plain smtplib over STARTTLS rather
than a SaaS email API: no new dependency, no vendor lock-in, works with
whatever mailbox already receives support@marketripple.in (Zoho/Google
Workspace/etc — the account isn't provisioned with a specific API-based
provider today).

SMTP credentials never reach the frontend — this module is backend-only,
and the request that triggers an email always returns success/failure
based on whether the DB write succeeded, not whether the email sent (see
callers). A missing/misconfigured SMTP_HOST just logs a warning and no-ops
rather than raising, so email delivery is best-effort, not a hard
dependency for the feature it supports.
"""
from __future__ import annotations

import asyncio
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


def _send_sync(to: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        log.warning("email.not_configured", subject=subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(body)
    try:
        # Port 465 is implicit TLS (the connection is encrypted from the
        # first byte) — calling starttls() on it hangs/fails because the
        # server never speaks plaintext SMTP to upgrade from. Port 587 (and
        # 25) is the opposite: plaintext first, then upgraded via STARTTLS.
        # Hostinger's smtp.hostinger.com, like most providers, only offers
        # 465, so this needs to branch on port rather than always STARTTLS.
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        return True
    except Exception as exc:
        log.warning("email.send_failed", error=str(exc), subject=subject)
        return False


async def send_email(to: str, subject: str, body: str) -> bool:
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, _send_sync, to, subject, body),
            timeout=15.0,
        )
    except Exception as exc:
        log.warning("email.send_timeout", error=str(exc), subject=subject)
        return False

from __future__ import annotations

import asyncio
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


class EmailSender(Protocol):
    async def send_password_reset_email(self, *, to: str, reset_url: str) -> None: ...


class EmailDeliveryError(RuntimeError):
    """Covers both "not configured" (Settings leaves email config optional,
    app/core/config.py, so the rest of the app runs fine unconfigured — this
    is where that gets enforced, only when the feature is actually used, not
    at process startup) and a real SES send failure. AuthService catches this
    broadly either way — see request_password_reset's note on why a send
    failure must never surface differently than "email not found"."""


def _build_password_reset_email(*, to: str, reset_url: str, expire_minutes: int) -> dict:
    subject = "Reset your ScoreWise password"
    text_body = (
        f"We got a request to reset your ScoreWise password.\n\n"
        f"Reset it here: {reset_url}\n\n"
        f"This link expires in {expire_minutes} minutes. "
        f"If you didn't request this, you can safely ignore this email — your password won't change."
    )
    html_body = (
        f"<p>We got a request to reset your ScoreWise password.</p>"
        f'<p><a href="{reset_url}">Reset your password</a></p>'
        f"<p>This link expires in {expire_minutes} minutes. "
        f"If you didn't request this, you can safely ignore this email — your password won't change.</p>"
    )
    return {
        "Destination": {"ToAddresses": [to]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    }


class SesEmailSender:
    """boto3 is sync, so the actual send_email call runs in a thread
    (asyncio.to_thread) to avoid blocking the event loop — the same care this
    app takes elsewhere with any slow sync call in an async request path.

    The boto3 client is built lazily, on first send, not in __init__: this
    class is constructed on *every* auth-service request (get_auth_service in
    deps.py depends on it unconditionally, since login/register/refresh/logout
    all share one AuthService), so building it eagerly would mean an
    unconfigured AWS_REGION breaks login itself, not just password reset.
    boto3.client(..., region_name=None) raises NoRegionError immediately at
    construction if no region is resolvable from any source — confirmed
    directly against this environment (no AWS_REGION set) before writing this
    comment, not assumed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):  # noqa: ANN202 — boto3 has no exported client type to annotate with
        if self._client is None:
            self._client = boto3.client(
                "ses",
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
            )
        return self._client

    async def send_password_reset_email(self, *, to: str, reset_url: str) -> None:
        if not self._settings.email_from:
            raise EmailDeliveryError(
                "EMAIL_FROM is not configured — set it (and AWS_REGION / a verified SES sender identity) "
                "before password reset emails can be sent."
            )
        message = _build_password_reset_email(
            to=to, reset_url=reset_url, expire_minutes=self._settings.password_reset_token_expire_minutes
        )

        def _send() -> None:
            client = self._get_client()
            client.send_email(Source=self._settings.email_from, **message)

        try:
            await asyncio.to_thread(_send)
        except (BotoCoreError, ClientError) as exc:
            raise EmailDeliveryError(f"SES send_email failed: {exc}") from exc

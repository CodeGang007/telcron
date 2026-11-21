"""Sends verification codes by email. The ONLY code that talks to an email provider; replaced
wholesale in tests. `log` (local) sends nothing: locally the codes come back in the sign-up response.
`smtp` sends through an SMTP server (Gmail with an app password while Telcron has no mail domain).
`ses` sends through Amazon SES with the host's IAM role (no keys)."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import get_settings

log = logging.getLogger("telcron.mailer")


class SendFailed(Exception):
    pass


def _body(code: str, minutes: int) -> tuple[str, str, str]:
    subject = f"{code} is your Telcron code"
    text = (f"Your Telcron verification code is {code}.\n\nIt expires in {minutes} minutes. "
            "If you did not ask for it, ignore this email: nobody can use your address without it.\n")
    html = (f"<div style=\"font-family:system-ui,sans-serif;max-width:480px;margin:auto;padding:24px\">"
            f"<p style=\"color:#7a0a12;font-weight:700;letter-spacing:.1em;font-size:12px\">TELCRON</p>"
            f"<p>Your verification code is</p>"
            f"<p style=\"font-size:32px;font-weight:800;letter-spacing:.3em;margin:8px 0\">{code}</p>"
            f"<p style=\"color:#5b6475\">It expires in {minutes} minutes. If you did not ask for it, "
            f"ignore this email.</p></div>")
    return subject, text, html


def _send_ses(to: str, code: str) -> None:
    import boto3  # imported here: only the deployed API needs it

    s = get_settings()
    subject, text, html = _body(code, s.code_ttl_minutes)
    boto3.client("sesv2", region_name=s.aws_region).send_email(
        FromEmailAddress=s.mail_from, Destination={"ToAddresses": [to]},
        Content={"Simple": {"Subject": {"Data": subject},
                            "Body": {"Text": {"Data": text}, "Html": {"Data": html}}}})


def _send_smtp(to: str, code: str) -> None:
    s = get_settings()
    subject, text, html = _body(code, s.code_ttl_minutes)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, s.mail_from, to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        # MAIL_FROM may carry a display name ("Telcron <a@b>"); the login is the bare address.
        smtp.login(s.smtp_user or parseaddr(s.mail_from or "")[1], s.smtp_password or "")
        smtp.send_message(msg)


async def send_code(to: str, code: str) -> None:
    s = get_settings()
    if s.mail_provider not in ("ses", "smtp"):
        log.info("mail provider %s: not sending the code to %s", s.mail_provider, to)
        return
    if not s.mail_from:
        raise SendFailed("MAIL_FROM is not set")
    if s.mail_provider == "smtp" and not s.smtp_password:
        raise SendFailed("SMTP_PASSWORD is not set")
    try:
        await asyncio.to_thread(_send_smtp if s.mail_provider == "smtp" else _send_ses, to, code)
    except Exception as exc:  # the provider refused (sandbox recipient, quota): the caller records it
        raise SendFailed(f"{type(exc).__name__}: {exc}"[:300]) from exc

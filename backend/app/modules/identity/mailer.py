"""Sends verification codes, and the sign-up notice, by email. The ONLY code that talks to an email
provider; replaced wholesale in tests. `log` (local) sends nothing: locally the codes come back in
the sign-up response.
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
    """The message did not go out. `code` is ours or the provider's error code, never its text:
    provider text can carry the recipient's address and is not ours to store (DEF-048)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# (subject, plain text, html)
Message = tuple[str, str, str]


def mask(address: str) -> str:
    """`j***@example.com`: enough to tell two log lines apart, not enough to name anyone."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _html(*paragraphs: str) -> str:
    return ("<div style=\"font-family:system-ui,sans-serif;max-width:480px;margin:auto;padding:24px\">"
            "<p style=\"color:#7a0a12;font-weight:700;letter-spacing:.1em;font-size:12px\">TELCRON</p>"
            + "".join(paragraphs) + "</div>")


def _body(code: str, minutes: int) -> Message:
    subject = f"{code} is your Telcron code"
    text = (f"Your Telcron verification code is {code}.\n\nIt expires in {minutes} minutes. "
            "If you did not ask for it, ignore this email: nobody can use your address without it.\n")
    html = _html("<p>Your verification code is</p>",
                 f"<p style=\"font-size:32px;font-weight:800;letter-spacing:.3em;margin:8px 0\">{code}</p>",
                 f"<p style=\"color:#5b6475\">It expires in {minutes} minutes. If you did not ask for it, "
                 "ignore this email.</p>")
    return subject, text, html


def _notice_body() -> Message:
    """Sent instead of a code when someone signs up with an address that already has an account,
    so the sign-up page answers the same either way (DEF-043)."""
    subject = "Someone tried to create a Telcron account with your email"
    text = ("Someone just tried to create a Telcron account with this email address. It already "
            "has an account, so nothing was changed.\n\nIf it was you, sign in instead. If it was "
            "not you, you can ignore this email: nobody can use your account without your "
            "password.\n")
    html = _html("<p>Someone just tried to create a Telcron account with this email address. It "
                 "already has an account, so nothing was changed.</p>",
                 "<p style=\"color:#5b6475\">If it was you, sign in instead. If it was not you, you "
                 "can ignore this email: nobody can use your account without your password.</p>")
    return subject, text, html


def _send_ses(to: str, message: Message) -> None:
    import boto3  # imported here: only the deployed API needs it

    s = get_settings()
    subject, text, html = message
    boto3.client("sesv2", region_name=s.aws_region).send_email(
        FromEmailAddress=s.mail_from, Destination={"ToAddresses": [to]},
        Content={"Simple": {"Subject": {"Data": subject},
                            "Body": {"Text": {"Data": text}, "Html": {"Data": html}}}})


def _send_smtp(to: str, message: Message) -> None:
    s = get_settings()
    subject, text, html = message
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, s.mail_from, to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        # MAIL_FROM may carry a display name ("Telcron <a@b>"); the login is the bare address.
        smtp.login(s.smtp_user or parseaddr(s.mail_from or "")[1], s.smtp_password or "")
        smtp.send_message(msg)


def _error_code(exc: Exception) -> str:
    """SES says `MessageRejected`, SMTP says 550: keep that, drop the sentence around it."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
        if isinstance(code, str) and code:
            return code[:60]
    smtp_code = getattr(exc, "smtp_code", None)
    if isinstance(smtp_code, int):
        return f"smtp_{smtp_code}"
    return type(exc).__name__[:60]


async def _send(to: str, message: Message, what: str) -> None:
    s = get_settings()
    if s.mail_provider not in ("ses", "smtp"):
        log.info("mail provider %s: not sending the %s to %s", s.mail_provider, what, mask(to))
        return
    if not s.mail_from:
        raise SendFailed("mail_from_unset")
    if s.mail_provider == "smtp" and not s.smtp_password:
        raise SendFailed("smtp_password_unset")
    try:
        await asyncio.to_thread(_send_smtp if s.mail_provider == "smtp" else _send_ses, to, message)
    except Exception as exc:  # the provider refused (sandbox recipient, quota): the caller records it
        code = _error_code(exc)
        log.warning("%s to %s not sent: %s", what, mask(to), code)
        raise SendFailed(code) from exc


async def send_code(to: str, code: str) -> None:
    await _send(to, _body(code, get_settings().code_ttl_minutes), "code")


async def send_signup_notice(to: str) -> None:
    await _send(to, _notice_body(), "sign-up notice")

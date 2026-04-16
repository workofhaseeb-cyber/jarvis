"""
Email Write Mode — Opt-in email sending for JARVIS.
By default JARVIS is READ-ONLY for email. This module adds WRITE capability
only when EMAIL_WRITE_ENABLED=true in .env.

Supports:
    - Gmail via SMTP (App Password)
    - Any SMTP server

Required .env vars (only needed if EMAIL_WRITE_ENABLED=true):
    EMAIL_WRITE_ENABLED=true
    EMAIL_SMTP_HOST=smtp.gmail.com
    EMAIL_SMTP_PORT=587
    EMAIL_ADDRESS=your@gmail.com
    EMAIL_APP_PASSWORD=your_app_password
    EMAIL_DISPLAY_NAME=JARVIS

For Gmail App Password:
    1. Enable 2FA on your Google account
    2. Go to myaccount.google.com/apppasswords
    3. Create app password for "Mail"
    4. Use that 16-char password as EMAIL_APP_PASSWORD
"""

import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger("jarvis.email_write")

EMAIL_WRITE_ENABLED = os.getenv("EMAIL_WRITE_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
DISPLAY_NAME = os.getenv("EMAIL_DISPLAY_NAME", "JARVIS")


def can_send_email() -> bool:
    """Check if email sending is configured and enabled."""
    return (
        EMAIL_WRITE_ENABLED
        and bool(EMAIL_ADDRESS)
        and bool(EMAIL_APP_PASSWORD)
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    reply_to: Optional[str] = None,
    html: bool = False,
) -> dict:
    """
    Send an email via SMTP.
    Returns {"success": bool, "message": str}
    """
    if not EMAIL_WRITE_ENABLED:
        return {
            "success": False,
            "message": "Email write mode is disabled. Set EMAIL_WRITE_ENABLED=true in .env to enable."
        }

    if not can_send_email():
        return {
            "success": False,
            "message": "Email credentials not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env."
        }

    try:
        msg = MIMEMultipart("alternative" if html else "mixed")
        msg["From"] = f"{DISPLAY_NAME} <{EMAIL_ADDRESS}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

        if cc:
            msg["Cc"] = cc
        if reply_to:
            msg["Reply-To"] = reply_to

        if html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        context = ssl.create_default_context()
        recipients = [to] + ([cc] if cc else [])

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipients, msg.as_string())

        log.info(f"Email sent to {to}: {subject}")
        return {"success": True, "message": f"Email sent to {to}."}

    except smtplib.SMTPAuthenticationError:
        log.error("SMTP authentication failed. Check EMAIL_APP_PASSWORD.")
        return {
            "success": False,
            "message": "Authentication failed. Check your email app password in .env."
        }
    except smtplib.SMTPRecipientsRefused:
        log.error(f"Recipient refused: {to}")
        return {"success": False, "message": f"Recipient address {to} was refused by the server."}
    except Exception as e:
        log.error(f"Email send failed: {e}")
        return {"success": False, "message": f"Failed to send email: {str(e)}"}


def compose_email_from_voice(
    raw_command: str,
    to: str,
    subject: str,
    body: str,
) -> dict:
    """
    Entry point for JARVIS voice commands like:
    'Send an email to john@example.com, subject meeting tomorrow, say I'll be there at 9 AM'
    """
    log.info(f"Voice email compose: to={to}, subject={subject}")
    return send_email(to=to, subject=subject, body=body)


EMAIL_SEND_TRIGGERS = [
    "send an email",
    "send email",
    "email to",
    "write an email",
    "compose an email",
    "draft an email",
    "reply to",
    "forward this",
]


def is_email_send_request(text: str) -> bool:
    """Check if user wants to send an email."""
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in EMAIL_SEND_TRIGGERS)

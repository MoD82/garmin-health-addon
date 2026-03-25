# src/output/email_sender.py
"""E-Mail-Report-Versand via SMTP mit Jinja2-Template."""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import Config

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _render_email(result: dict, blocks: dict, is_weekly: bool = False) -> str:
    """Rendert das Jinja2 HTML-Template und gibt HTML-String zurück."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("report_email.html")
    return template.render(result=result, blocks=blocks, is_weekly=is_weekly)


def _send_smtp(config: Config, subject: str, html_body: str) -> None:
    """Synchroner SMTP-Versand — wird via asyncio.to_thread aufgerufen."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.email_user
    msg["To"] = config.email_recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(config.email_smtp_host, config.email_smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.email_user, config.email_password)
        smtp.sendmail(config.email_user, [config.email_recipient], msg.as_string())


async def send_report(
    config: Config,
    result: dict,
    blocks: dict,
    is_weekly: bool = False,
) -> bool:
    """
    Rendert HTML-Template und versendet per SMTP.

    Returns:
        True wenn Versand erfolgreich, False bei Fehler oder fehlendem Config.
    """
    if not config.email_user or not config.email_password or not config.email_recipient:
        logger.warning("E-Mail nicht konfiguriert — überspringe Versand")
        return False

    try:
        html_body = _render_email(result, blocks, is_weekly)
        prefix = "Wochenbericht" if is_weekly else "Tagesbericht"
        subject = f"🚴 Coach {prefix} — {result.get('date', '')}"
        await asyncio.to_thread(_send_smtp, config, subject, html_body)
        logger.info("E-Mail versendet an %s", config.email_recipient)
        return True
    except Exception as exc:
        logger.error("E-Mail-Versand fehlgeschlagen: %s", exc)
        return False

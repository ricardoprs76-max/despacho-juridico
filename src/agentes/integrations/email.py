"""Where 'enviar_correo' sends: an outbox folder by default, SMTP if configured."""

import os
import re
import smtplib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> str: ...


def _build(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    if not _ADDRESS_RE.fullmatch(to):
        raise ValueError(f"Dirección de correo no válida: {to!r}")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


class OutboxMailer:
    """Writes each email as an .eml file instead of sending it."""

    def __init__(self, folder: Path, sender: str = "agente@ejemplo.com") -> None:
        self.folder = folder
        self.sender = sender

    def send(self, to: str, subject: str, body: str) -> str:
        message = _build(self.sender, to, subject, body)
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        slug = _SLUG_RE.sub("-", subject.lower()).strip("-")[:40] or "correo"
        path = self.folder / f"{stamp}-{slug}.eml"
        path.write_bytes(message.as_bytes())
        return f"Correo guardado en la bandeja de salida: {path.name}"


class SmtpMailer:
    """Sends through an SMTP server with STARTTLS."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sender: str,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self.host, self.port = host, port
        self.user, self._password = user, password
        self.sender = sender
        self._smtp_factory = smtp_factory

    def send(self, to: str, subject: str, body: str) -> str:
        message = _build(self.sender, to, subject, body)
        with self._smtp_factory(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self._password)
            smtp.send_message(message)
        return f"Correo enviado a {to}."


def mailer_from_env(data_dir: Path, env: Mapping[str, str] | None = None) -> Mailer:
    env = os.environ if env is None else env
    host = env.get("SMTP_HOST", "").strip()
    if not host:
        return OutboxMailer(data_dir / "bandeja_salida")
    user = env.get("SMTP_USER", "").strip()
    return SmtpMailer(
        host=host,
        port=int(env.get("SMTP_PORT", "").strip() or 587),
        user=user,
        password=env.get("SMTP_PASSWORD", ""),
        sender=env.get("SMTP_FROM", "").strip() or user,
    )

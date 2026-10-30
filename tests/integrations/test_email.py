import email
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any, ClassVar

import pytest

from agentes.integrations import OutboxMailer, SmtpMailer, mailer_from_env


def test_outbox_writes_eml(tmp_path: Path) -> None:
    mailer = OutboxMailer(tmp_path / "salida")
    message = mailer.send("ana@ejemplo.com", "Cotización ñandú", "¿Te sirve mañana?")
    [file] = list((tmp_path / "salida").glob("*.eml"))
    assert message == f"Correo guardado en la bandeja de salida: {file.name}"
    parsed = email.message_from_bytes(file.read_bytes(), _class=EmailMessage, policy=policy.default)
    assert parsed["To"] == "ana@ejemplo.com"
    assert parsed["Subject"] == "Cotización ñandú"
    body = parsed.get_body()
    assert body is not None
    assert body.get_content().strip() == "¿Te sirve mañana?"


def test_outbox_two_mails_two_files(tmp_path: Path) -> None:
    mailer = OutboxMailer(tmp_path)
    mailer.send("a@b.co", "Uno", "x")
    mailer.send("a@b.co", "Uno", "x")
    assert len(list(tmp_path.glob("*.eml"))) == 2


@pytest.mark.parametrize("bad", ["", "sin-arroba", "a@b", "a b@c.co", "a@b.co\nBcc: x@y.co"])
def test_invalid_recipient_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="Dirección de correo no válida"):
        OutboxMailer(tmp_path).send(bad, "Asunto", "Cuerpo")


class FakeSMTP:
    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        self.host, self.port = host, port
        self.calls: list[str] = []
        self.sent: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *args: object) -> None:
        self.calls.append("quit")

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login:{user}")

    def send_message(self, msg: EmailMessage) -> None:
        self.calls.append("send")
        self.sent.append(msg)


def test_smtp_uses_starttls_and_login() -> None:
    FakeSMTP.instances.clear()
    mailer = SmtpMailer("smtp.ejemplo.com", 587, "user", "pw", "tienda@ejemplo.com", FakeSMTP)
    assert mailer.send("ana@ejemplo.com", "Hola", "Cuerpo") == "Correo enviado a ana@ejemplo.com."
    [smtp] = FakeSMTP.instances
    assert (smtp.host, smtp.port) == ("smtp.ejemplo.com", 587)
    assert smtp.calls == ["starttls", "login:user", "send", "quit"]
    assert smtp.sent[0]["From"] == "tienda@ejemplo.com"


def test_mailer_from_env_defaults_to_outbox(tmp_path: Path) -> None:
    mailer = mailer_from_env(tmp_path, env={})
    assert isinstance(mailer, OutboxMailer)
    assert mailer.folder == tmp_path / "bandeja_salida"


def test_mailer_from_env_smtp(tmp_path: Path) -> None:
    env = {"SMTP_HOST": "smtp.x.co", "SMTP_USER": "u", "SMTP_PASSWORD": "p", "SMTP_FROM": "a@x.co"}
    mailer = mailer_from_env(tmp_path, env=env)
    assert isinstance(mailer, SmtpMailer)
    assert mailer.port == 587

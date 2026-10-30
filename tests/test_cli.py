from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentes.cli import app
from agentes.llm import API_KEY_ENV
from tests.conftest import EXAMPLE_CONFIG

runner = CliRunner()
DEMO_NOTICE = "Modo demo: no hay clave de IA configurada. Las respuestas son de ejemplo."


@pytest.fixture(autouse=True)
def no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    backend_vars = ["GOOGLE_SERVICE_ACCOUNT_FILE", "AGENTES_SHEET_ID", "SMTP_HOST"]
    for var in [*API_KEY_ENV.values(), *backend_vars]:
        monkeypatch.delenv(var, raising=False)


def chat(tmp_path: Path, stdin: str) -> str:
    db = tmp_path / "sub" / "memoria.sqlite"
    result = runner.invoke(app, ["chat", str(EXAMPLE_CONFIG), "--db", str(db)], input=stdin)
    assert result.exit_code == 0, result.output
    return result.output


def test_validate_ok() -> None:
    result = runner.invoke(app, ["validate", str(EXAMPLE_CONFIG)])
    assert result.exit_code == 0
    assert "Configuración válida: Ferretería El Tornillo" in result.output


def test_validate_missing_file_exit_2_no_traceback(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2
    assert "No se encontró el archivo de configuración" in result.output
    assert "Traceback" not in result.output


def test_chat_missing_file_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["chat", str(tmp_path / "nope.yaml")], input="")
    assert result.exit_code == 2
    assert "No se encontró el archivo de configuración" in result.output


def test_chat_demo_notice_and_reply(tmp_path: Path) -> None:
    output = chat(tmp_path, "hola\nsalir\n")
    assert output.count(DEMO_NOTICE) == 1
    assert "Ferretería El Tornillo: [modo demo] ¡Hola!" in output
    assert (tmp_path / "sub" / "memoria.sqlite").exists()


def test_chat_blank_line_reprompts(tmp_path: Path) -> None:
    output = chat(tmp_path, "\n   \nhola\nsalir\n")
    assert output.count("Tú: ") == 4
    assert output.count("Ferretería El Tornillo: ") == 1


def test_chat_exit_word(tmp_path: Path) -> None:
    output = chat(tmp_path, "SALIR\nhola\n")
    assert output.rstrip().endswith("¡Hasta pronto!")
    assert "[modo demo]" not in output


def test_chat_eof_ends_politely(tmp_path: Path) -> None:
    assert chat(tmp_path, "hola\n").rstrip().endswith("¡Hasta pronto!")


def test_chat_accented_output(tmp_path: Path) -> None:
    output = chat(tmp_path, "¿Hola, señor?\nsalir\n")
    assert "[modo demo]" in output
    assert "�" not in output


def test_chat_provider_error_keeps_loop_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agentes.agent import Agent, AgentError

    def boom(self: Agent, thread_id: str, text: str) -> str:
        raise AgentError("límite de uso alcanzado")

    monkeypatch.setattr(Agent, "ask", boom)
    output = chat(tmp_path, "hola\nsalir\n")
    assert "No se pudo obtener respuesta del modelo: límite de uso alcanzado" in output
    assert "Traceback" not in output
    assert output.rstrip().endswith("¡Hasta pronto!")


def test_chat_ctrl_c_ends_politely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert chat(tmp_path, "").rstrip().endswith("¡Hasta pronto!")


def test_dotenv_file_is_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "placeholder")
    monkeypatch.delenv("GOOGLE_API_KEY")
    (tmp_path / ".env").write_text("GOOGLE_API_KEY=clave-del-env\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate", str(EXAMPLE_CONFIG)])
    assert result.exit_code == 0
    import os

    assert os.environ["GOOGLE_API_KEY"] == "clave-del-env"


def test_piped_accented_input_reaches_memory_intact(tmp_path: Path) -> None:
    import subprocess
    import sys

    from agentes.agent import Agent
    from agentes.config import load_config
    from agentes.llm import build_chat_model

    db = tmp_path / "m.sqlite"
    env = {k: v for k, v in __import__("os").environ.items() if k not in API_KEY_ENV.values()}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from agentes.cli import app; app()",
            "chat",
            str(EXAMPLE_CONFIG),
            "--db",
            str(db),
        ],
        input="¿Hola, señor?\nsalir\n".encode(),
        env=env,
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    config = load_config(EXAMPLE_CONFIG)
    with Agent(config, build_chat_model(config.model, env={}), db_path=db) as agent:
        assert agent.history("default")[0].content == "¿Hola, señor?"


def chat_in(tmp_path: Path, stdin: str) -> str:
    """Chat using --data so memory, outbox and sheet live under tmp_path/data."""
    data = tmp_path / "data"
    result = runner.invoke(app, ["chat", str(EXAMPLE_CONFIG), "--data", str(data)], input=stdin)
    assert result.exit_code == 0, result.output
    return result.output


def outbox_files(tmp_path: Path) -> list[Path]:
    return list((tmp_path / "data" / "bandeja_salida").glob("*.eml"))


def test_chat_search_shows_source(tmp_path: Path) -> None:
    output = chat_in(tmp_path, "¿Cuál es el horario?\nsalir\n")
    assert "Fuente: horarios.md" in output


def test_chat_email_confirm_yes_writes_outbox(tmp_path: Path) -> None:
    output = chat_in(tmp_path, "Mándale un correo al cliente\nsí\nsalir\n")
    assert (
        'Acción pendiente: Enviar correo a cliente@ejemplo.com con asunto "Mensaje de prueba"'
        in output
    )
    assert "¿Confirmas? (s/n): " in output
    assert len(outbox_files(tmp_path)) == 1


def test_chat_email_confirm_no_cancels(tmp_path: Path) -> None:
    output = chat_in(tmp_path, "Mándale un correo al cliente\nn\nsalir\n")
    assert "El usuario canceló la acción." in output
    assert outbox_files(tmp_path) == []


def test_chat_confirmation_reasks_on_invalid_answer(tmp_path: Path) -> None:
    output = chat_in(tmp_path, "Mándale un correo al cliente\nquizás\ns\nsalir\n")
    assert output.count("¿Confirmas? (s/n): ") == 2
    assert len(outbox_files(tmp_path)) == 1


def test_chat_resumes_pending_on_restart(tmp_path: Path) -> None:
    chat_in(tmp_path, "Mándale un correo al cliente\n")  # EOF while the question is open
    assert outbox_files(tmp_path) == []
    output = chat_in(tmp_path, "s\nsalir\n")
    assert output.index("Acción pendiente:") < output.index("¿Confirmas?")
    assert len(outbox_files(tmp_path)) == 1


def test_auditoria_lists_entries(tmp_path: Path) -> None:
    chat_in(tmp_path, "Mándale un correo al cliente\nn\n¿Cuál es el horario?\nsalir\n")
    data = str(tmp_path / "data")
    result = runner.invoke(app, ["auditoria", str(EXAMPLE_CONFIG), "--data", data])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert len(lines) == 2
    assert "| default | buscar_documentos | ejecutada |" in lines[0]
    assert "| default | enviar_correo | cancelada |" in lines[1]
    assert '"para": "cliente@ejemplo.com"' in lines[1]


def test_auditoria_empty(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["auditoria", str(EXAMPLE_CONFIG), "--data", str(tmp_path / "vacio")]
    )
    assert result.exit_code == 0
    assert result.output.strip() == "No hay acciones registradas."
    assert not (tmp_path / "vacio").exists()


def test_chat_prints_knowledge_warnings(tmp_path: Path) -> None:
    config = tmp_path / "c.yaml"
    config.write_text(
        "id: x\ncompany_name: X\nsector: s\ntone: t\n"
        "tools: [buscar_documentos]\nknowledge_dir: no-existe\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["chat", str(config), "--data", str(tmp_path / "d")], input="salir\n"
    )
    assert f"Aviso: La carpeta de documentos no existe: {tmp_path / 'no-existe'}" in result.output

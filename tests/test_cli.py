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
    for var in API_KEY_ENV.values():
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

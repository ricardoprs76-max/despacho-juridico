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

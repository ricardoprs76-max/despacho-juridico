from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agentes.cli import app
from agentes.llm import API_KEY_ENV
from tests.conftest import EXAMPLE_CONFIG

runner = CliRunner()
REFUSED = "Sin AGENTES_API_KEY solo se permite --host 127.0.0.1 o localhost."


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No .env from the repo folder, no real keys or backends.
    monkeypatch.chdir(tmp_path)
    extra = ["GOOGLE_SERVICE_ACCOUNT_FILE", "AGENTES_SHEET_ID", "SMTP_HOST", "AGENTES_API_KEY"]
    for var in [*API_KEY_ENV.values(), *extra]:
        monkeypatch.delenv(var, raising=False)


def fake_uvicorn(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def run(asgi: Any, host: str, port: int, **kwargs: Any) -> None:
        seen.update(host=host, port=port)
        client = TestClient(asgi)
        seen["health"] = client.get("/health").json()

    monkeypatch.setattr("uvicorn.run", run)
    return seen


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5"])
def test_serve_refuses_public_host_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host: str
) -> None:
    seen = fake_uvicorn(monkeypatch)
    args = ["serve", str(EXAMPLE_CONFIG), "--host", host, "--data", str(tmp_path / "d")]
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert REFUSED in result.output
    assert seen == {}


def test_serve_runs_uvicorn_in_demo_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = fake_uvicorn(monkeypatch)
    result = runner.invoke(app, ["serve", str(EXAMPLE_CONFIG), "--data", str(tmp_path / "d")])
    assert result.exit_code == 0, result.output
    assert (seen["host"], seen["port"]) == ("127.0.0.1", 8000)
    assert seen["health"]["company"] == "Ferretería El Tornillo"
    assert seen["health"]["demo"] is True
    assert seen["health"]["auth"] is False
    assert "Modo demo" in result.output
    assert "Abre http://127.0.0.1:8000 en el navegador." in result.output


def test_serve_public_host_with_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTES_API_KEY", "s3creta")
    seen = fake_uvicorn(monkeypatch)
    args = ["serve", str(EXAMPLE_CONFIG), "--host", "0.0.0.0", "--port", "9000"]
    result = runner.invoke(app, [*args, "--data", str(tmp_path / "d")])
    assert result.exit_code == 0, result.output
    assert (seen["host"], seen["port"]) == ("0.0.0.0", 9000)
    assert seen["health"]["auth"] is True
    assert "s3creta" not in result.output


def test_serve_missing_config_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["serve", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2
    assert "No se encontró el archivo de configuración" in result.output

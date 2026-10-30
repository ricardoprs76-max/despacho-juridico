import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from typer.testing import CliRunner

from agentes.agent import Agent
from agentes.cli import app
from agentes.config import AgentConfig, load_config
from agentes.llm import API_KEY_ENV
from agentes.mcp import build_mcp_server
from tests.api.conftest import EMAIL_ARGS, make_config, outbox
from tests.conftest import EXAMPLE_CONFIG, RecordingChatModel, selection_for

LAW_CONFIG = EXAMPLE_CONFIG.parent / "despacho-juridico.yaml"


def make_agent(tmp_path: Path, replies: list[Any], config: AgentConfig | None = None) -> Agent:
    return Agent(
        config or make_config(tmp_path),
        selection_for(RecordingChatModel(replies=replies)),
        db_path=tmp_path / "data" / "m.sqlite",
        env={},
    )


@pytest.fixture
def agents(tmp_path: Path) -> Iterator[list[Agent]]:
    opened: list[Agent] = []
    yield opened
    for agent in opened:
        agent.close()


def call(agent: Agent, tool: str, args: dict[str, Any]) -> str:
    result = asyncio.run(build_mcp_server(agent).call_tool(tool, args))
    return "".join(getattr(part, "text", "") for part in result.content)


def tool_names(agent: Agent) -> set[str]:
    return {t.name for t in asyncio.run(build_mcp_server(agent).list_tools())}


def email_call() -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "enviar_correo", "args": EMAIL_ARGS, "id": "c1"}])


def test_run_tool_audits_read_only(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [], load_config(LAW_CONFIG))
    agents.append(agent)
    args = {"actuacion": "reposicion", "fecha_notificacion": "02/03/2026"}
    text = agent.run_tool("calcular_plazo", args)
    assert "Vence el 05/03/2026" in text
    [entry] = agent.audit.entries()
    assert (entry.thread_id, entry.tool, entry.status) == ("mcp", "calcular_plazo", "executed")


def test_run_tool_bad_args_is_audited_error(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [], load_config(LAW_CONFIG))
    agents.append(agent)
    text = agent.run_tool("calcular_plazo", {"actuacion": "reposicion"})
    assert text.startswith("Argumentos no válidos para calcular_plazo")
    [entry] = agent.audit.entries()
    assert entry.status == "error"


def test_run_tool_refuses_side_effects(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [])
    agents.append(agent)
    with pytest.raises(ValueError, match="efectos"):
        agent.run_tool("enviar_correo", EMAIL_ARGS)
    with pytest.raises(ValueError, match="no está disponible"):
        agent.run_tool("calcular_plazo", {})
    assert outbox(tmp_path) == []
    assert agent.audit.entries() == []


def test_mcp_lists_only_safe_tools(tmp_path: Path, agents: list[Agent]) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    shop = make_agent(tmp_path / "a", [])
    law = make_agent(tmp_path / "b", [], load_config(LAW_CONFIG))
    agents += [shop, law]
    assert tool_names(shop) == {"preguntar", "confirmar", "buscar_documentos"}
    assert tool_names(law) == {"preguntar", "confirmar", "buscar_documentos", "calcular_plazo"}


def test_mcp_preguntar_and_confirmar_flow(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [email_call(), "Listo, correo enviado."])
    agents.append(agent)
    server = build_mcp_server(agent)

    async def flow() -> tuple[str, str]:
        asked = await server.call_tool("preguntar", {"mensaje": "envía la cotización"})
        done = await server.call_tool("confirmar", {"aprobar": True})
        return asked.content[0].text, done.content[0].text  # type: ignore[union-attr]

    asked, done = asyncio.run(flow())
    assert asked.startswith("Acción pendiente: Enviar correo a ana@ejemplo.com")
    assert asked.endswith("Llama a confirmar con aprobar=true o false.")
    assert done == "Listo, correo enviado."
    assert len(outbox(tmp_path)) == 1
    [entry] = agent.audit.entries()
    assert (entry.thread_id, entry.status) == ("mcp", "executed")


def test_mcp_direct_search(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [])
    agents.append(agent)
    assert "(Fuente: horarios.md)" in call(agent, "buscar_documentos", {"consulta": "horario"})


def test_mcp_errors_are_text(tmp_path: Path, agents: list[Agent]) -> None:
    agent = make_agent(tmp_path, [RuntimeError("cuota agotada")])
    agents.append(agent)
    nothing = call(agent, "confirmar", {"aprobar": True})
    assert nothing == "No hay ninguna acción pendiente de confirmar."
    failed = call(agent, "preguntar", {"mensaje": "hola"})
    assert failed == "No se pudo obtener respuesta del modelo: cuota agotada"


def test_mcp_command_keeps_stdout_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for var in API_KEY_ENV.values():
        monkeypatch.delenv(var, raising=False)
    ran: list[str] = []
    monkeypatch.setattr(
        "mcp.server.MCPServer.run", lambda self, transport="stdio", **kw: ran.append(self.name)
    )
    result = CliRunner().invoke(app, ["mcp", str(EXAMPLE_CONFIG), "--data", str(tmp_path / "d")])
    assert result.exit_code == 0, result.output
    assert ran == ["Ferretería El Tornillo"]
    assert result.stdout == ""
    assert "Modo demo" in result.stderr

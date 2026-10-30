from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agentes.agent import Agent, AgentReply
from agentes.config import AgentConfig
from agentes.llm import DemoChatModel, ModelSelection
from tests.conftest import RecordingChatModel, selection_for

EMAIL_ARGS = {"para": "ana@ejemplo.com", "asunto": "Cotización", "cuerpo": "Adjunto precios."}


def call(name: str, args: dict[str, Any], call_id: str = "c1") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def make_config(tmp_path: Path, **overrides: Any) -> AgentConfig:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "horarios.md").write_text("El horario es de 8 a 6.", encoding="utf-8")
    fields: dict[str, Any] = {
        "id": "t",
        "company_name": "Ferretería",
        "sector": "ventas",
        "tone": "amable",
        "tools": ["buscar_documentos", "registrar_en_hoja", "enviar_correo"],
        "confirm_tools": ["registrar_en_hoja", "enviar_correo"],
        "knowledge_dir": docs,
    }
    fields.update(overrides)
    return AgentConfig(**fields)


def make_agent(
    tmp_path: Path,
    model: RecordingChatModel | DemoChatModel,
    config: AgentConfig | None = None,
) -> Agent:
    selection = (
        ModelSelection(model, is_demo=True, provider="demo", model_name="demo")
        if isinstance(model, DemoChatModel)
        else selection_for(model)
    )
    return Agent(
        config or make_config(tmp_path),
        selection,
        db_path=tmp_path / "data" / "m.sqlite",
        env={},
    )


def outbox(tmp_path: Path) -> list[Path]:
    return list((tmp_path / "data" / "bandeja_salida").glob("*.eml"))


def test_read_only_tool_runs_without_confirmation_and_is_audited(tmp_path: Path) -> None:
    model = RecordingChatModel(
        replies=[call("buscar_documentos", {"consulta": "horario"}), "Abrimos de 8 a 6."]
    )
    with make_agent(tmp_path, model) as agent:
        reply = agent.ask("t1", "¿Horario?")
        assert reply == AgentReply(text="Abrimos de 8 a 6.")
        tool_result = model.calls[1][-1]
        assert isinstance(tool_result, ToolMessage)
        assert "(Fuente: horarios.md)" in tool_result.text
        [entry] = agent.audit.entries()
    assert (entry.tool, entry.status) == ("buscar_documentos", "executed")


def test_side_effect_tool_waits_for_confirmation(tmp_path: Path) -> None:
    model = RecordingChatModel(replies=[call("enviar_correo", EMAIL_ARGS)])
    with make_agent(tmp_path, model) as agent:
        reply = agent.ask("t1", "Envíale la cotización a Ana")
        assert reply.pending is not None
        assert reply.pending.tool == "enviar_correo"
        assert reply.pending.args == EMAIL_ARGS
        expected = 'Enviar correo a ana@ejemplo.com con asunto "Cotización"'
        assert reply.pending.description == expected
        assert agent.pending("t1") == reply.pending
        assert agent.audit.entries() == []
    assert outbox(tmp_path) == []


def test_confirm_executes_and_audits(tmp_path: Path) -> None:
    model = RecordingChatModel(replies=[call("enviar_correo", EMAIL_ARGS), "Listo, enviado."])
    with make_agent(tmp_path, model) as agent:
        agent.ask("t1", "Envíale la cotización a Ana")
        reply = agent.confirm("t1", approved=True)
        assert reply == AgentReply(text="Listo, enviado.")
        assert agent.pending("t1") is None
        [entry] = agent.audit.entries()
    assert entry.status == "executed"
    assert entry.args == EMAIL_ARGS
    assert len(outbox(tmp_path)) == 1


def test_reject_cancels_and_audits(tmp_path: Path) -> None:
    model = RecordingChatModel(
        replies=[call("enviar_correo", EMAIL_ARGS), "Entendido, no lo envío."]
    )
    with make_agent(tmp_path, model) as agent:
        agent.ask("t1", "Envíale la cotización a Ana")
        reply = agent.confirm("t1", approved=False)
        assert reply.text == "Entendido, no lo envío."
        assert model.calls[1][-1].text == "El usuario canceló la acción."
        [entry] = agent.audit.entries()
    assert entry.status == "rejected"
    assert outbox(tmp_path) == []


def test_pending_survives_restart(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    first = RecordingChatModel(replies=[call("enviar_correo", EMAIL_ARGS)])
    with make_agent(tmp_path, first, config) as agent:
        agent.ask("t1", "Envíale la cotización a Ana")
    with make_agent(tmp_path, RecordingChatModel(replies=["Enviado."]), config) as agent:
        pending = agent.pending("t1")
        assert pending is not None
        assert pending.tool == "enviar_correo"
        assert agent.confirm("t1", approved=True).text == "Enviado."
    assert len(outbox(tmp_path)) == 1


def test_ask_while_pending_rejected(tmp_path: Path) -> None:
    model = RecordingChatModel(replies=[call("enviar_correo", EMAIL_ARGS)])
    with make_agent(tmp_path, model) as agent:
        agent.ask("t1", "Envíale la cotización a Ana")
        with pytest.raises(ValueError, match="Primero confirma o cancela la acción pendiente"):
            agent.ask("t1", "otra cosa")


def test_confirm_without_pending_raises(tmp_path: Path) -> None:
    with (
        make_agent(tmp_path, RecordingChatModel(replies=[])) as agent,
        pytest.raises(ValueError, match="No hay ninguna acción pendiente de confirmar"),
    ):
        agent.confirm("t1", approved=True)


def test_disabled_tool_call_not_executed(tmp_path: Path) -> None:
    config = make_config(tmp_path, tools=["buscar_documentos"], confirm_tools=[])
    model = RecordingChatModel(
        replies=[call("enviar_correo", EMAIL_ARGS), "No puedo enviar correos."]
    )
    with make_agent(tmp_path, model, config) as agent:
        assert agent.ask("t1", "Envía un correo").text == "No puedo enviar correos."
        assert model.calls[1][-1].text == "La herramienta enviar_correo no está disponible."
        [entry] = agent.audit.entries()
    assert entry.status == "error"
    assert outbox(tmp_path) == []


def test_invalid_args_reported_as_error_without_confirmation(tmp_path: Path) -> None:
    model = RecordingChatModel(
        replies=[call("enviar_correo", {"para": "ana@ejemplo.com"}), "Me faltan datos."]
    )
    with make_agent(tmp_path, model) as agent:
        reply = agent.ask("t1", "Envía un correo a Ana")
        assert reply.pending is None
        assert reply.text == "Me faltan datos."
        assert model.calls[1][-1].text.startswith("Argumentos no válidos para enviar_correo:")
        assert agent.audit.entries()[0].status == "error"


def test_backend_failure_audited_as_error_and_reply_continues(tmp_path: Path) -> None:
    (tmp_path / "data" / "hoja.csv").mkdir(parents=True)  # a folder where the CSV should go
    model = RecordingChatModel(
        replies=[call("registrar_en_hoja", {"datos": {"cliente": "Ana"}}), "No pude registrarlo."]
    )
    with make_agent(tmp_path, model) as agent:
        agent.ask("t1", "Anota a Ana")
        reply = agent.confirm("t1", approved=True)
        assert reply.text == "No pude registrarlo."
        assert model.calls[1][-1].text.startswith("Error al ejecutar registrar_en_hoja:")
        assert agent.audit.entries()[0].status == "error"


def test_two_confirmations_in_one_turn_execute_once_each(tmp_path: Path) -> None:
    both = AIMessage(
        "",
        tool_calls=[
            {"name": "registrar_en_hoja", "args": {"datos": {"cliente": "Ana"}}, "id": "a"},
            {"name": "enviar_correo", "args": EMAIL_ARGS, "id": "b"},
        ],
    )
    model = RecordingChatModel(replies=[both, "Hecho."])
    with make_agent(tmp_path, model) as agent:
        first = agent.ask("t1", "Anota a Ana y escríbele")
        assert first.pending is not None
        assert first.pending.tool == "registrar_en_hoja"
        second = agent.confirm("t1", approved=True)
        assert second.pending is not None
        assert second.pending.tool == "enviar_correo"
        assert agent.confirm("t1", approved=False).text == "Hecho."
        statuses = sorted((e.tool, e.status) for e in agent.audit.entries())
    assert statuses == [("enviar_correo", "rejected"), ("registrar_en_hoja", "executed")]
    rows = (tmp_path / "data" / "hoja.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(rows) == 2  # header + exactly one row


def test_demo_mode_end_to_end_search(tmp_path: Path) -> None:
    with make_agent(tmp_path, DemoChatModel()) as agent:
        reply = agent.ask("t1", "¿Cuál es el horario?")
    assert reply.text.startswith("[modo demo] Resultado:")
    assert "Fuente: horarios.md" in reply.text


def test_knowledge_warnings_exposed(tmp_path: Path) -> None:
    config = make_config(tmp_path, knowledge_dir=tmp_path / "no-existe")
    with make_agent(tmp_path, RecordingChatModel(replies=[]), config) as agent:
        expected = f"La carpeta de documentos no existe: {tmp_path / 'no-existe'}"
        assert agent.warnings == (expected,)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agentes.llm import DemoChatModel

SYSTEM = SystemMessage("Eres el asistente virtual de Ferretería El Tornillo, una empresa...")


def reply(text: str) -> str:
    result = DemoChatModel().invoke([SYSTEM, HumanMessage(text)])
    assert isinstance(result, AIMessage)
    assert isinstance(result.content, str)
    return result.content


def test_demo_greeting_mentions_company() -> None:
    answer = reply("¡Hola! buenos días")
    assert answer.startswith("[modo demo] ")
    assert "Ferretería El Tornillo" in answer


def test_demo_other_question_gets_generic_answer() -> None:
    answer = reply("¿Cuánto cuesta un martillo?")
    assert answer.startswith("[modo demo] ")
    assert "modo demo no puedo consultar información real" in answer


def test_demo_reply_is_deterministic() -> None:
    assert reply("¿Tienen tornillos?") == reply("¿Tienen tornillos?")


@tool
def buscar_documentos(consulta: str) -> str:
    """Busca en los documentos."""
    return consulta


@tool
def enviar_correo(para: str, asunto: str, cuerpo: str) -> str:
    """Envía un correo."""
    return para


def test_bind_tools_returns_copy_with_names() -> None:
    model = DemoChatModel()
    bound = model.bind_tools([buscar_documentos])
    assert isinstance(bound, DemoChatModel)
    assert bound is not model
    assert bound.tool_names == frozenset({"buscar_documentos"})
    assert model.tool_names == frozenset()


def demo_call(model: DemoChatModel, text: str) -> AIMessage:
    result = model.invoke([SYSTEM, HumanMessage(text)])
    assert isinstance(result, AIMessage)
    return result


def test_demo_calls_search_tool_when_bound() -> None:
    model = DemoChatModel().bind_tools([buscar_documentos])
    assert isinstance(model, DemoChatModel)
    result = demo_call(model, "¿Cuál es el horario?")
    assert result.tool_calls[0]["name"] == "buscar_documentos"
    assert result.tool_calls[0]["args"] == {"consulta": "¿Cuál es el horario?"}
    assert result.tool_calls[0]["id"] == "demo-2"


def test_demo_does_not_call_unbound_tool() -> None:
    result = demo_call(DemoChatModel(), "¿Cuál es el horario?")
    assert result.tool_calls == []


def test_demo_calls_email_tool() -> None:
    model = DemoChatModel().bind_tools([enviar_correo])
    assert isinstance(model, DemoChatModel)
    call = demo_call(model, "Mándame un correo con la cotización").tool_calls[0]
    assert call["name"] == "enviar_correo"
    assert call["args"]["para"] == "cliente@ejemplo.com"


def test_demo_summarizes_tool_result() -> None:
    model = DemoChatModel().bind_tools([buscar_documentos])
    messages = [
        SYSTEM,
        HumanMessage("¿horario?"),
        AIMessage("", tool_calls=[{"name": "buscar_documentos", "args": {}, "id": "demo-2"}]),
        ToolMessage("Abrimos de 8 a 6 (Fuente: horarios.md)", tool_call_id="demo-2"),
    ]
    result = model.invoke(messages)
    assert result.content == "[modo demo] Resultado: Abrimos de 8 a 6 (Fuente: horarios.md)"


def test_demo_greeting_whole_word_only() -> None:
    assert "modo demo no puedo consultar" in reply("la chola llegó")

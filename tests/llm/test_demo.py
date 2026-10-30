import pytest
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


def test_demo_sheet_args_use_field_list() -> None:
    @tool
    def registrar_en_hoja(datos: list[dict[str, str]]) -> str:
        """Registra."""
        return "ok"

    model = DemoChatModel().bind_tools([registrar_en_hoja])
    assert isinstance(model, DemoChatModel)
    call = demo_call(model, "Anota que llamó Ana").tool_calls[0]
    assert call["args"] == {"datos": [{"campo": "nota", "valor": "Anota que llamó Ana"}]}


def test_demo_greeting_whole_word_only() -> None:
    assert "modo demo no puedo consultar" in reply("la chola llegó")


@tool
def calcular_plazo(
    actuacion: str, fecha_notificacion: str, notificacion_electronica: bool = False
) -> str:
    """Calcula un plazo."""
    return actuacion


def plazo_args(text: str) -> dict[str, object] | None:
    model = DemoChatModel().bind_tools([calcular_plazo])
    assert isinstance(model, DemoChatModel)
    calls = demo_call(model, text).tool_calls
    return calls[0]["args"] if calls else None


def test_demo_calls_plazo_tool() -> None:
    assert plazo_args("¿Cuándo vence la reposición notificada el 02/03/2026?") == {
        "actuacion": "reposicion",
        "fecha_notificacion": "02/03/2026",
        "notificacion_electronica": False,
    }


@pytest.mark.parametrize(
    ("text", "actuacion"),
    [
        ("plazo para apelar la sentencia notificada el 2026-03-02", "apelacion_sentencia"),
        ("término de la apelación del auto del 02/03/2026", "apelacion_auto"),
        (
            "plazo para contestar en verbal sumario, notificado 02/03/2026",
            "contestacion_verbal_sumario",
        ),
        ("plazo para contestar la demanda notificada 02/03/2026", "contestacion_verbal"),
        ("término de excepciones notificado el 02/03/2026", "excepciones_ejecutivo"),
        ("plazo para impugnar la tutela del 02/03/2026", "impugnacion_tutela"),
        ("plazo para apelar la sentencia de tutela del 02/03/2026", "impugnacion_tutela"),
        (
            "plazo para responder la petición de documentos del 02/03/2026",
            "respuesta_peticion_documentos",
        ),
        (
            "plazo para responder la consulta en derecho de petición del 02/03/2026",
            "respuesta_peticion_consulta",
        ),
        ("plazo de respuesta a la petición radicada el 02/03/2026", "respuesta_derecho_peticion"),
    ],
)
def test_demo_plazo_actuacion_keywords(text: str, actuacion: str) -> None:
    args = plazo_args(text)
    assert args is not None
    assert args["actuacion"] == actuacion


def test_demo_plazo_electronic_flag() -> None:
    args = plazo_args("plazo de excepciones, notificación personal electrónica del 02/03/2026")
    assert args is not None
    assert args["notificacion_electronica"] is True


def test_demo_plazo_without_date_no_call() -> None:
    assert plazo_args("¿Cuál es el plazo de la reposición?") is None


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuánto cuesta la consulta?",
        "¿Hacen domicilios?",
        "¿Cómo me preparo para el examen?",
        "Revisa la cláusula quinta del contrato",
        "¿Puedo cancelar mi cita?",
        "¿Cuál es la tarifa?",
    ],
)
def test_demo_searches_sector_questions(text: str) -> None:
    model = DemoChatModel().bind_tools([buscar_documentos])
    assert isinstance(model, DemoChatModel)
    assert demo_call(model, text).tool_calls[0]["name"] == "buscar_documentos"


def test_demo_email_word_does_not_set_electronic_flag() -> None:
    args = plazo_args("me llegó por correo el auto, ¿plazo de reposición? 02/03/2026")
    assert args is not None
    assert args["notificacion_electronica"] is False

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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


def test_demo_bind_tools_returns_self() -> None:
    @tool
    def buscar(texto: str) -> str:
        """Busca algo."""
        return texto

    model = DemoChatModel()
    assert model.bind_tools([buscar]) is model

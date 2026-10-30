from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agentes.agent import Agent
from agentes.config import AgentConfig
from tests.conftest import RecordingChatModel, selection_for


def make_agent(config: AgentConfig, model: RecordingChatModel, db: Path) -> Agent:
    return Agent(config, selection_for(model), db_path=db)


def test_ask_returns_model_reply(example_config: AgentConfig, tmp_path: Path) -> None:
    model = RecordingChatModel(replies=["Claro, tenemos martillos."])
    with make_agent(example_config, model, tmp_path / "m.sqlite") as agent:
        assert agent.ask("t1", "¿Tienen martillos?") == "Claro, tenemos martillos."


def test_system_prompt_sent_but_not_stored(example_config: AgentConfig, tmp_path: Path) -> None:
    model = RecordingChatModel(replies=["ok"])
    with make_agent(example_config, model, tmp_path / "m.sqlite") as agent:
        agent.ask("t1", "hola")
        sent = model.calls[0]
        assert isinstance(sent[0], SystemMessage)
        assert sent[0].content == example_config.system_prompt()
        history = agent.history("t1")
    assert not any(isinstance(m, SystemMessage) for m in history)
    assert [type(m) for m in history] == [HumanMessage, AIMessage]


def test_memory_within_thread(example_config: AgentConfig, tmp_path: Path) -> None:
    model = RecordingChatModel(replies=["Mucho gusto, Ana.", "Te llamas Ana."])
    with make_agent(example_config, model, tmp_path / "m.sqlite") as agent:
        agent.ask("t1", "Me llamo Ana")
        agent.ask("t1", "¿Cómo me llamo?")
    contents = [m.content for m in model.calls[1][1:]]
    assert contents == ["Me llamo Ana", "Mucho gusto, Ana.", "¿Cómo me llamo?"]


def test_threads_isolated(example_config: AgentConfig, tmp_path: Path) -> None:
    model = RecordingChatModel(replies=["uno", "dos"])
    with make_agent(example_config, model, tmp_path / "m.sqlite") as agent:
        agent.ask("cliente-a", "Hola, soy A")
        agent.ask("cliente-b", "Hola, soy B")
    assert [m.content for m in model.calls[1][1:]] == ["Hola, soy B"]


def test_memory_survives_restart(example_config: AgentConfig, tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    with make_agent(example_config, RecordingChatModel(replies=["Anotado."]), db) as agent:
        agent.ask("t1", "Mi pedido es el 42")
    with make_agent(example_config, RecordingChatModel(replies=[]), db) as agent:
        history = agent.history("t1")
    assert [m.content for m in history] == ["Mi pedido es el 42", "Anotado."]


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_message_rejected_without_model_call(
    example_config: AgentConfig, tmp_path: Path, text: str
) -> None:
    model = RecordingChatModel(replies=[])
    with (
        make_agent(example_config, model, tmp_path / "m.sqlite") as agent,
        pytest.raises(ValueError, match=r"El mensaje está vacío\."),
    ):
        agent.ask("t1", text)
    assert model.calls == []


def test_ask_strips_text(example_config: AgentConfig, tmp_path: Path) -> None:
    model = RecordingChatModel(replies=["ok"])
    with make_agent(example_config, model, tmp_path / "m.sqlite") as agent:
        agent.ask("t1", "  hola  ")
    assert model.calls[0][-1].content == "hola"


def test_is_demo_reflects_selection(example_config: AgentConfig, tmp_path: Path) -> None:
    with make_agent(example_config, RecordingChatModel(replies=[]), tmp_path / "m.sqlite") as a:
        assert a.is_demo is False

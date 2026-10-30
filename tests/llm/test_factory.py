import pytest

from agentes.config import ModelConfig
from agentes.llm import DemoChatModel, build_chat_model


def test_no_key_returns_demo() -> None:
    selection = build_chat_model(ModelConfig(provider="gemini"), env={})
    assert selection.is_demo
    assert isinstance(selection.model, DemoChatModel)
    assert selection.provider == "demo"


def test_blank_key_returns_demo() -> None:
    selection = build_chat_model(ModelConfig(provider="openai"), env={"OPENAI_API_KEY": "   "})
    assert selection.is_demo


@pytest.mark.parametrize(
    ("provider", "env_var", "class_name", "default_model"),
    [
        ("gemini", "GOOGLE_API_KEY", "ChatGoogleGenerativeAI", "gemini-2.5-flash"),
        ("anthropic", "ANTHROPIC_API_KEY", "ChatAnthropic", "claude-haiku-5-5"),
        ("openai", "OPENAI_API_KEY", "ChatOpenAI", "gpt-4.1-mini"),
    ],
)
def test_key_builds_provider_model(
    provider: str, env_var: str, class_name: str, default_model: str
) -> None:
    selection = build_chat_model(
        ModelConfig(provider=provider),  # type: ignore[arg-type]
        env={env_var: "clave-de-prueba"},
    )
    assert not selection.is_demo
    assert type(selection.model).__name__ == class_name
    assert selection.provider == provider
    assert selection.model_name == default_model


def test_explicit_model_name_overrides_default() -> None:
    selection = build_chat_model(
        ModelConfig(provider="openai", model="gpt-4.1"), env={"OPENAI_API_KEY": "k"}
    )
    assert selection.model_name == "gpt-4.1"

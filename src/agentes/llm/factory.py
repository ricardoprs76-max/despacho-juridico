"""Pick the chat model for a config: a real provider when a key exists, else demo."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from agentes.config import ModelConfig
from agentes.llm.demo import DemoChatModel

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-4.1-mini",
}
API_KEY_ENV: dict[str, str] = {
    "gemini": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass(frozen=True)
class ModelSelection:
    """The chosen model plus what the UI needs to tell the user about it."""

    model: BaseChatModel
    is_demo: bool
    provider: str
    model_name: str


def build_chat_model(cfg: ModelConfig, env: Mapping[str, str] | None = None) -> ModelSelection:
    """Build the provider's chat model, or the demo model if its API key is missing."""
    env = os.environ if env is None else env
    key = env.get(API_KEY_ENV[cfg.provider], "").strip()
    if not key:
        return ModelSelection(DemoChatModel(), is_demo=True, provider="demo", model_name="demo")

    name = cfg.model or DEFAULT_MODELS[cfg.provider]
    secret = SecretStr(key)
    model: BaseChatModel
    # Provider packages are imported lazily so unused ones cost nothing at startup.
    if cfg.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(model=name, api_key=secret, temperature=cfg.temperature)
    elif cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        # ChatAnthropic's stubs mark optional fields (timeout, stop) as required.
        model = ChatAnthropic(  # type: ignore[call-arg]
            model_name=name, api_key=secret, temperature=cfg.temperature
        )
    else:
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model=name, api_key=secret, temperature=cfg.temperature)
    return ModelSelection(model, is_demo=False, provider=cfg.provider, model_name=name)

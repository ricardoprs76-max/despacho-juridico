"""A deterministic, offline chat model so the project runs without any API key."""

import re
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

DEMO_PREFIX = "[modo demo] "
GREETING_WORDS = ("hola", "buenos días", "buenas tardes", "buenas noches", "buenas")
GENERIC_ANSWER = (
    "En modo demo no puedo consultar información real. Configura una clave de IA "
    "(por ejemplo GOOGLE_API_KEY, que es gratis) para obtener respuestas de verdad."
)
_COMPANY_RE = re.compile(r"asistente virtual de (.+?), una empresa")


def _company_from(messages: Sequence[BaseMessage]) -> str:
    for message in messages:
        if isinstance(message, SystemMessage) and isinstance(message.content, str):
            match = _COMPANY_RE.search(message.content)
            if match:
                return match.group(1)
    return "la empresa"


def _last_human_text(messages: Sequence[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return message.content
    return ""


class DemoChatModel(BaseChatModel):
    """Answers with canned Spanish replies chosen by keyword."""

    @property
    def _llm_type(self) -> str:
        return "demo"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = _last_human_text(messages).lower()
        if any(word in text for word in GREETING_WORDS):
            answer = f"¡Hola! Soy el asistente de {_company_from(messages)}. ¿En qué te ayudo?"
        else:
            answer = GENERIC_ANSWER
        message = AIMessage(content=DEMO_PREFIX + answer)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """The demo model never calls tools, so binding is a no-op."""
        return self

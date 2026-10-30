"""Shared test fixtures: example config and a scripted, recording chat model."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agentes.config import AgentConfig, load_config
from agentes.llm import ModelSelection

EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "ejemplo.yaml"


class RecordingChatModel(BaseChatModel):
    """Replies with scripted answers in order and records every input it receives."""

    # str | AIMessage | BaseException (Any: pydantic cannot validate exception instances)
    replies: list[Any]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        answer = self.replies[len(self.calls) - 1]
        if isinstance(answer, BaseException):
            raise answer
        message = answer if isinstance(answer, AIMessage) else AIMessage(content=answer)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> "RecordingChatModel":
        return self


@pytest.fixture
def example_config() -> AgentConfig:
    return load_config(EXAMPLE_CONFIG)


def selection_for(model: BaseChatModel) -> ModelSelection:
    return ModelSelection(model, is_demo=False, provider="test", model_name="recording")

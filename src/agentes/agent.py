"""High-level facade: one company's agent with persistent conversations."""

import sqlite3
import uuid
from pathlib import Path
from types import TracebackType
from typing import Self

from langchain_core.messages import AnyMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from agentes.config import AgentConfig
from agentes.graph import build_graph
from agentes.llm import ModelSelection


class AgentError(Exception):
    """The model could not answer (network, invalid key, rate limit...)."""


class Agent:
    """Chat with a company's agent; each thread_id is a separate conversation."""

    def __init__(self, config: AgentConfig, selection: ModelSelection, db_path: Path) -> None:
        self.config = config
        self.selection = selection
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            self._graph = build_graph(config, selection.model, SqliteSaver(self._conn))
        except Exception:
            self._conn.close()
            raise

    @property
    def is_demo(self) -> bool:
        return self.selection.is_demo

    def ask(self, thread_id: str, text: str) -> str:
        """Send one user message and return the agent's reply text."""
        text = text.strip()
        if not text:
            raise ValueError("El mensaje está vacío.")
        run_config = self._run_config(thread_id)
        message = HumanMessage(text, id=str(uuid.uuid4()))
        try:
            result = self._graph.invoke({"messages": [message]}, run_config)
        except Exception as exc:
            # Drop the unanswered question so the next turn doesn't see two in a row.
            if any(m.id == message.id for m in self.history(thread_id)):
                self._graph.update_state(
                    run_config, {"messages": [RemoveMessage(id=str(message.id))]}
                )
            raise AgentError(str(exc)) from exc
        return str(result["messages"][-1].text)

    def history(self, thread_id: str) -> list[AnyMessage]:
        """All stored messages of a conversation, oldest first."""
        snapshot = self._graph.get_state(self._run_config(thread_id))
        messages: list[AnyMessage] = snapshot.values.get("messages", [])
        return messages

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @staticmethod
    def _run_config(thread_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": thread_id}}

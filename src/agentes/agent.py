"""High-level facade: one company's agent with persistent conversations."""

import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agentes.audit import AuditLog
from agentes.config import AgentConfig
from agentes.graph import build_graph
from agentes.llm import ModelSelection
from agentes.tools import build_context, build_tools, fields_to_row


class AgentError(Exception):
    """The model could not answer (network, invalid key, rate limit...)."""


@dataclass(frozen=True)
class PendingAction:
    """A side-effecting tool call waiting for the user's yes or no."""

    tool: str
    args: dict[str, Any]
    description: str


@dataclass(frozen=True)
class AgentReply:
    text: str
    pending: PendingAction | None = None


BODY_PREVIEW = 160


def describe(tool: str, args: Mapping[str, Any]) -> str:
    """One Spanish line telling the user what the agent is about to do."""
    if tool == "enviar_correo":
        body = " ".join(str(args.get("cuerpo", "")).split())
        if len(body) > BODY_PREVIEW:
            body = body[:BODY_PREVIEW].rstrip() + "…"
        return (
            f'Enviar correo a {args.get("para", "?")} con asunto "{args.get("asunto", "")}". '
            f'Texto: "{body}"'
        )
    if tool == "registrar_en_hoja":
        try:
            row = fields_to_row(list(args.get("datos") or []))
        except Exception:
            row = {}
        return "Registrar en la hoja: " + ", ".join(f"{k}={v}" for k, v in row.items())
    return f"Ejecutar {tool} con {dict(args)}"


class Agent:
    """Chat with a company's agent; each thread_id is a separate conversation."""

    def __init__(
        self,
        config: AgentConfig,
        selection: ModelSelection,
        db_path: Path,
        data_dir: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.selection = selection
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        # The checkpointer writes from LangGraph's worker threads and manages its own
        # transactions, so the audit log gets a separate connection to the same file.
        self._audit_conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        try:
            context = build_context(config, data_dir or db_path.parent, env)
            self.warnings = context.warnings
            self.audit = AuditLog(self._audit_conn)
            self._graph = build_graph(
                config,
                selection.model,
                SqliteSaver(self._conn),
                tools=build_tools(config, context),
                audit=self.audit,
            )
        except Exception:
            self.close()
            raise

    @property
    def is_demo(self) -> bool:
        return self.selection.is_demo

    def ask(self, thread_id: str, text: str) -> AgentReply:
        """Send one user message; the reply may carry an action awaiting confirmation."""
        text = text.strip()
        if not text:
            raise ValueError("El mensaje está vacío.")
        if self.pending(thread_id) is not None:
            raise ValueError("Primero confirma o cancela la acción pendiente.")
        message = HumanMessage(text, id=str(uuid.uuid4()))
        before = {m.id for m in self.history(thread_id)}
        try:
            self._graph.invoke({"messages": [message]}, self._run_config(thread_id))
        except KeyboardInterrupt:
            self._discard_turn(thread_id, before)
            raise
        except Exception as exc:
            self._discard_turn(thread_id, before)
            raise AgentError(str(exc)) from exc
        return self._reply(thread_id)

    def confirm(self, thread_id: str, approved: bool) -> AgentReply:
        """Answer the pending action with yes (run it) or no (cancel it)."""
        if self.pending(thread_id) is None:
            raise ValueError("No hay ninguna acción pendiente de confirmar.")
        try:
            self._graph.invoke(Command(resume=approved), self._run_config(thread_id))
        except Exception as exc:
            raise AgentError(str(exc)) from exc
        return self._reply(thread_id)

    def pending(self, thread_id: str) -> PendingAction | None:
        """The action waiting for confirmation, read from the checkpoint (survives restarts)."""
        snapshot = self._graph.get_state(self._run_config(thread_id))
        for item in snapshot.interrupts:
            value = item.value
            if isinstance(value, dict) and "tool" in value:
                args = dict(value.get("args") or {})
                return PendingAction(value["tool"], args, describe(value["tool"], args))
        return None

    def history(self, thread_id: str) -> list[AnyMessage]:
        """All stored messages of a conversation, oldest first."""
        snapshot = self._graph.get_state(self._run_config(thread_id))
        messages: list[AnyMessage] = snapshot.values.get("messages", [])
        return messages

    def close(self) -> None:
        self._audit_conn.close()
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

    def _reply(self, thread_id: str) -> AgentReply:
        pending = self.pending(thread_id)
        if pending is not None:
            return AgentReply(text="", pending=pending)
        last = next(
            (m for m in reversed(self.history(thread_id)) if isinstance(m, AIMessage)), None
        )
        return AgentReply(text=str(last.text) if last is not None else "")

    def _discard_turn(self, thread_id: str, before: set[str | None]) -> None:
        # Drop everything this failed turn added so the next turn starts clean.
        added = [m for m in self.history(thread_id) if m.id not in before]
        # If a tool already ran, keep the turn: the model and the user must still see
        # that the email was sent, or a retry would send it twice.
        if any(isinstance(m, ToolMessage) for m in added):
            return
        if added:
            removals = [RemoveMessage(id=str(m.id)) for m in added]
            self._graph.update_state(self._run_config(thread_id), {"messages": removals})

    @staticmethod
    def _run_config(thread_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": thread_id}}

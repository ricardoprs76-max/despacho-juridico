"""Compile the agent's LangGraph graph: model, tools, human confirmation, audit."""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from agentes.audit import AuditLog, AuditStatus
from agentes.config import AgentConfig
from agentes.graph.state import AgentState

MODEL_NODE = "model"
TOOLS_NODE = "tools"
CANCELLED = "El usuario canceló la acción."


def invalid_args(tool: BaseTool, args: dict[str, Any]) -> str | None:
    """Spanish description of why args don't fit the tool's schema, or None if they do."""
    schema = tool.args_schema
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        return None
    try:
        schema.model_validate(args)
    except ValidationError as exc:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        return f"Argumentos no válidos para {tool.name}: revisa {fields}."
    return None


def build_graph(
    config: AgentConfig,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[Any] | None,
    tools: Sequence[BaseTool] = (),
    audit: AuditLog | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build START -> model -> (tools -> model)* -> END.

    The system prompt is added at call time and never stored, so editing the
    config changes the behaviour of existing conversations too.
    """
    agent_config = config
    system = SystemMessage(config.system_prompt())
    by_name = {tool.name: tool for tool in tools}
    runnable: Runnable[Any, Any] = model.bind_tools(list(tools)) if tools else model

    def problem_with(call: ToolCall) -> str | None:
        tool = by_name.get(call["name"])
        if tool is None:
            return f"La herramienta {call['name']} no está disponible."
        return invalid_args(tool, call["args"])

    def execute(call: ToolCall, problem: str | None, approved: bool) -> tuple[AuditStatus, str]:
        if problem is not None:
            return "error", problem
        if not approved:
            return "rejected", CANCELLED
        try:
            return "executed", str(by_name[call["name"]].invoke(call["args"]))
        except Exception as exc:
            return "error", f"Error al ejecutar {call['name']}: {exc}"

    def call_model(state: AgentState) -> dict[str, list[Any]]:
        return {"messages": [runnable.invoke([system, *state["messages"]])]}

    def route(state: AgentState) -> str:
        last = state["messages"][-1]
        return TOOLS_NODE if isinstance(last, AIMessage) and last.tool_calls else END

    # LangGraph injects the run config only into a parameter named exactly "config".
    def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, list[Any]]:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        thread_id = str(config.get("configurable", {}).get("thread_id", ""))
        calls = list(last.tool_calls)
        problems = [problem_with(call) for call in calls]

        # Collect every confirmation BEFORE running anything: LangGraph re-runs this
        # node from the top on each resume, so executing first would repeat side effects.
        approvals = [True] * len(calls)
        for i, call in enumerate(calls):
            if problems[i] is None and call["name"] in agent_config.confirm_tools:
                payload = {"tool": call["name"], "args": call["args"], "tool_call_id": call["id"]}
                approvals[i] = bool(interrupt(payload))

        results = []
        for call, problem, approved in zip(calls, problems, approvals, strict=True):
            status, text = execute(call, problem, approved)
            if audit is not None:
                audit.record(thread_id, call["name"], call["args"], status, text)
            results.append(ToolMessage(text, tool_call_id=call["id"] or "", name=call["name"]))
        return {"messages": results}

    graph = StateGraph(AgentState)
    graph.add_node(MODEL_NODE, call_model)
    graph.add_node(TOOLS_NODE, run_tools)
    graph.add_edge(START, MODEL_NODE)
    graph.add_conditional_edges(MODEL_NODE, route, [TOOLS_NODE, END])
    graph.add_edge(TOOLS_NODE, MODEL_NODE)
    return graph.compile(checkpointer=checkpointer)

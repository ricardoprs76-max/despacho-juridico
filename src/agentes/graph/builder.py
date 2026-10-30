"""Compile the agent's LangGraph graph."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agentes.config import AgentConfig
from agentes.graph.state import AgentState

MODEL_NODE = "model"


def build_graph(
    config: AgentConfig,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[Any] | None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build START -> model -> END.

    The system prompt is added at call time and never stored, so editing the
    config changes the behaviour of existing conversations too.
    """
    system = SystemMessage(config.system_prompt())

    def call_model(state: AgentState) -> dict[str, list[Any]]:
        reply = model.invoke([system, *state["messages"]])
        return {"messages": [reply]}

    graph = StateGraph(AgentState)
    graph.add_node(MODEL_NODE, call_model)
    graph.add_edge(START, MODEL_NODE)
    graph.add_edge(MODEL_NODE, END)
    return graph.compile(checkpointer=checkpointer)

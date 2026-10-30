"""Conversation state carried through the LangGraph graph."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Messages of one conversation; new messages are appended, not replaced."""

    messages: Annotated[list[AnyMessage], add_messages]

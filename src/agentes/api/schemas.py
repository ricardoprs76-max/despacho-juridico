"""Request and response bodies of the HTTP API."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

THREAD_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
MAX_MESSAGE = 4000

ThreadId = Annotated[str, StringConstraints(pattern=THREAD_PATTERN)]
Message = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE)
]


class ChatRequest(BaseModel):
    message: Message = Field(description="Mensaje del usuario.")
    thread_id: ThreadId | None = Field(
        default=None, description="Conversación a continuar; si falta se crea una nueva."
    )


class ConfirmRequest(BaseModel):
    approved: bool = Field(description="true ejecuta la acción pendiente, false la cancela.")


class PendingOut(BaseModel):
    tool: str
    args: dict[str, Any]
    description: str


class ChatResponse(BaseModel):
    thread_id: str
    reply: str
    pending: PendingOut | None


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class HistoryResponse(BaseModel):
    thread_id: str
    messages: list[MessageOut]
    pending: PendingOut | None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    company: str
    sector: str
    demo: bool
    provider: str
    model: str
    auth: bool


class AuditEntryOut(BaseModel):
    id: int
    timestamp: datetime
    thread_id: str
    tool: str
    args: dict[str, Any]
    status: Literal["executed", "rejected", "error"]
    result: str

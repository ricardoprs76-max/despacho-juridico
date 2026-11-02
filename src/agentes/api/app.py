"""FastAPI service around one company's agent."""

import secrets
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi import Path as PathParam
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentes.agent import Agent, AgentError, AgentReply, PendingAction
from agentes.api.schemas import (
    THREAD_PATTERN,
    AuditEntryOut,
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    HealthResponse,
    HistoryResponse,
    MessageOut,
    PendingOut,
    ToolOut,
)

API_KEY_HEADER = "X-API-Key"
BAD_KEY = "Clave de API inválida o ausente."
MODEL_FAILED = "No se pudo obtener respuesta del modelo: {error}"
BAD_JSON = "El cuerpo debe ser JSON válido en UTF-8."
BAD_DATA = "Datos no válidos: revisa {fields}."
FASTAPI_BAD_BODY = "There was an error parsing the body"
STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_AUDIT = 50
MAX_AUDIT = 500

ThreadPath = Annotated[str, PathParam(pattern=THREAD_PATTERN)]


def _pending_out(pending: PendingAction | None) -> PendingOut | None:
    if pending is None:
        return None
    return PendingOut(tool=pending.tool, args=pending.args, description=pending.description)


def create_app(agent: Agent, api_key: str | None = None) -> FastAPI:
    """Build the app; the caller opens and closes the agent."""
    app = FastAPI(
        title=f"Agentes IA para Empresas — {agent.config.company_name}",
        description="Chat with a company's agent; side-effecting actions wait for a yes.",
        version="0.1.0",
    )
    # One turn at a time: SQLite checkpoints and pending-action checks are not safe for
    # concurrent turns, and serialising them makes a double click run an action once.
    lock = threading.Lock()
    app.state.agent_lock = lock

    @app.exception_handler(StarletteHTTPException)
    async def spanish_body_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 400 and exc.detail == FASTAPI_BAD_BODY:
            return JSONResponse(status_code=400, content={"detail": BAD_JSON})
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def spanish_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(status_code=422, content={"detail": BAD_JSON})
        # The first loc item is where the value came from (body, query, path).
        fields = sorted(
            {".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]) for e in errors}
        )
        return JSONResponse(
            status_code=422, content={"detail": BAD_DATA.format(fields=", ".join(fields))}
        )

    header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

    def require_key(given: Annotated[str | None, Depends(header)]) -> None:
        if api_key is None:
            return
        if given is None or not secrets.compare_digest(given.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail=BAD_KEY)

    def run(thread_id: str, action: Callable[[], AgentReply]) -> ChatResponse:
        with lock:
            try:
                reply = action()
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except AgentError as exc:
                raise HTTPException(status_code=502, detail=MODEL_FAILED.format(error=exc)) from exc
        return ChatResponse(
            thread_id=thread_id, reply=reply.text, pending=_pending_out(reply.pending)
        )

    @app.get("/health", tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            company=agent.config.company_name,
            fictitious=agent.config.fictitious,
            sector=agent.config.sector,
            demo=agent.is_demo,
            provider=agent.selection.provider,
            model=agent.selection.model_name,
            auth=api_key is not None,
            tools=[
                ToolOut(name=name, confirm=name in agent.config.confirm_tools)
                for name in agent.config.tools
            ],
        )

    protected = APIRouter(dependencies=[Depends(require_key)], tags=["chat"])

    @protected.post("/chat")
    def chat(body: ChatRequest) -> ChatResponse:
        thread_id = body.thread_id or uuid.uuid4().hex
        return run(thread_id, lambda: agent.ask(thread_id, body.message))

    @protected.post("/chat/{thread_id}/confirm")
    def confirm(thread_id: ThreadPath, body: ConfirmRequest) -> ChatResponse:
        return run(thread_id, lambda: agent.confirm(thread_id, body.approved))

    @protected.get("/chat/{thread_id}")
    def history(thread_id: ThreadPath) -> HistoryResponse:
        with lock:
            stored = agent.history(thread_id)
            pending = agent.pending(thread_id)
        messages: list[MessageOut] = []
        for m in stored:
            if isinstance(m, HumanMessage):
                messages.append(MessageOut(role="user", text=str(m.text)))
            elif isinstance(m, AIMessage) and str(m.text).strip():
                messages.append(MessageOut(role="assistant", text=str(m.text)))
        return HistoryResponse(
            thread_id=thread_id, messages=messages, pending=_pending_out(pending)
        )

    @protected.get("/audit", tags=["audit"])
    def audit(
        thread_id: Annotated[str | None, Query(pattern=THREAD_PATTERN)] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_AUDIT)] = DEFAULT_AUDIT,
    ) -> list[AuditEntryOut]:
        """Tool calls the agent executed, cancelled or failed; newest first."""
        with lock:
            entries = agent.audit.entries(thread_id=thread_id, limit=limit)
        return [AuditEntryOut.model_validate(e, from_attributes=True) for e in entries]

    app.include_router(protected)
    # Mounted last so every API route above wins over a file of the same name.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
    return app

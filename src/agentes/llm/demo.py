"""A deterministic, offline chat model so the project runs without any API key."""

import re
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

DEMO_PREFIX = "[modo demo] "
GENERIC_ANSWER = (
    "En modo demo no puedo consultar información real. Configura una clave de IA "
    "(por ejemplo GOOGLE_API_KEY, que es gratis) para obtener respuestas de verdad."
)
_GREETING_RE = re.compile(r"\b(hola|buenos días|buenas tardes|buenas noches|buenas)\b")
_SEARCH_RE = re.compile(
    r"\b(horario|precio|cuesta|cu[aá]nto|tarifa|costo|valor|pol[ií]tica|garant[ií]a|documento"
    r"|domicilio|examen|ex[aá]menes|cita|cancelar|contrato|cl[aá]usula|requisito|convenio)"
)
_SHEET_RE = re.compile(r"\b(registra|anota)")
_EMAIL_RE = re.compile(r"\b(correo|email)")
_DEADLINE_RE = re.compile(r"\b(plazo|t[ée]rmino|vence|vencimiento)")
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b")
# Checked in order: the first matching keyword set wins.
_ACTUACIONES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("tutela",), "impugnacion_tutela"),
    (("reposici",), "reposicion"),
    (("apela", "sentencia"), "apelacion_sentencia"),
    (("apela",), "apelacion_auto"),
    (("sumario",), "contestacion_verbal_sumario"),
    (("contesta",), "contestacion_verbal"),
    (("excepci",), "excepciones_ejecutivo"),
    (("petici", "document"), "respuesta_peticion_documentos"),
    (("petici", "consulta"), "respuesta_peticion_consulta"),
    (("petici",), "respuesta_derecho_peticion"),
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


def _tool_name(tool: dict[str, Any] | type | Callable[..., Any] | BaseTool) -> str:
    if isinstance(tool, BaseTool):
        return tool.name
    return str(convert_to_openai_tool(tool)["function"]["name"])


class DemoChatModel(BaseChatModel):
    """Answers with canned Spanish replies and calls bound tools by keyword."""

    tool_names: frozenset[str] = frozenset()

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
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    def _reply(self, messages: list[BaseMessage]) -> AIMessage:
        last = messages[-1] if messages else None
        if isinstance(last, ToolMessage):
            return AIMessage(content=f"{DEMO_PREFIX}Resultado: {last.text}")

        original = _last_human_text(messages)
        text = original.lower()
        call = self._tool_call_for(text, original, call_id=f"demo-{len(messages)}")
        if call is not None:
            return AIMessage(content="", tool_calls=[call])
        if _GREETING_RE.search(text):
            answer = f"¡Hola! Soy el asistente de {_company_from(messages)}. ¿En qué te ayudo?"
        else:
            answer = GENERIC_ANSWER
        return AIMessage(content=DEMO_PREFIX + answer)

    def _tool_call_for(self, text: str, original: str, call_id: str) -> ToolCall | None:
        date_match = _DATE_RE.search(text)
        if "calcular_plazo" in self.tool_names and _DEADLINE_RE.search(text) and date_match:
            actuacion = next(
                (key for words, key in _ACTUACIONES if all(w in text for w in words)),
                "reposicion",
            )
            args = {
                "actuacion": actuacion,
                "fecha_notificacion": date_match.group(1),
                # Only an explicit personal electronic notification; "me llegó por correo"
                # usually means an auto notified by estado.
                "notificacion_electronica": "personal" in text
                and ("electr" in text or "mensaje de datos" in text),
            }
            return ToolCall(name="calcular_plazo", args=args, id=call_id)
        if "buscar_documentos" in self.tool_names and _SEARCH_RE.search(text):
            return ToolCall(name="buscar_documentos", args={"consulta": original}, id=call_id)
        if "registrar_en_hoja" in self.tool_names and _SHEET_RE.search(text):
            return ToolCall(
                name="registrar_en_hoja",
                args={"datos": [{"campo": "nota", "valor": original}]},
                id=call_id,
            )
        if "enviar_correo" in self.tool_names and _EMAIL_RE.search(text):
            args = {
                "para": "cliente@ejemplo.com",
                "asunto": "Mensaje de prueba",
                "cuerpo": original,
            }
            return ToolCall(name="enviar_correo", args=args, id=call_id)
        return None

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Return a copy that knows which tools it may call."""
        return self.model_copy(update={"tool_names": frozenset(_tool_name(t) for t in tools)})

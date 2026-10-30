"""The built-in tools, wired to their backends for one company."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from agentes.config import AgentConfig
from agentes.integrations import Mailer, SheetBackend, mailer_from_env, sheet_from_env
from agentes.rag import (
    Bm25KnowledgeBase,
    KnowledgeBase,
    build_knowledge_base,
    format_hits,
    load_chunks,
)
from agentes.tool_names import SIDE_EFFECT_TOOLS


@dataclass(frozen=True)
class ToolContext:
    """Backends the tools act on, plus warnings to show the user at start."""

    knowledge: KnowledgeBase
    sheet: SheetBackend
    mailer: Mailer
    warnings: tuple[str, ...] = ()


def build_context(
    config: AgentConfig, data_dir: Path, env: Mapping[str, str] | None = None
) -> ToolContext:
    knowledge: KnowledgeBase = Bm25KnowledgeBase([])
    warnings: list[str] = []
    if "buscar_documentos" in config.tools:
        if config.knowledge_dir is None:
            warnings.append("buscar_documentos está activa pero no hay knowledge_dir configurado.")
        else:
            chunks, warnings = load_chunks(config.knowledge_dir)
            knowledge, kb_warnings = build_knowledge_base(chunks, env)
            warnings += kb_warnings
    for name in config.tools:
        if name in SIDE_EFFECT_TOOLS and name not in config.confirm_tools:
            warnings.append(f"{name} se ejecutará sin pedir confirmación.")
    return ToolContext(
        knowledge=knowledge,
        sheet=sheet_from_env(data_dir, env),
        mailer=mailer_from_env(data_dir, env),
        warnings=tuple(warnings),
    )


def _search(ctx: ToolContext) -> BaseTool:
    def buscar_documentos(consulta: str) -> str:
        return format_hits(ctx.knowledge.search(consulta))

    return StructuredTool.from_function(
        buscar_documentos,
        description=(
            "Busca en los documentos internos de la empresa (horarios, precios, políticas, "
            "procedimientos). Úsala antes de responder preguntas sobre la empresa y cita la "
            "fuente que devuelve."
        ),
    )


class Campo(BaseModel):
    """One column of the row: a field name and its value."""

    campo: str = Field(description="Nombre de la columna, por ejemplo 'cliente'.")
    valor: str = Field(description="Valor de la columna, por ejemplo 'Ana'.")


def fields_to_row(datos: list[Campo] | list[dict[str, str]]) -> dict[str, str]:
    row: dict[str, str] = {}
    for item in datos:
        field = item if isinstance(item, Campo) else Campo.model_validate(item)
        row[field.campo] = field.valor
    return row


def _sheet(ctx: ToolContext) -> BaseTool:
    # A list of {campo, valor} instead of a free-form dict: Gemini rejects JSON-schema
    # objects without declared properties.
    def registrar_en_hoja(datos: list[Campo]) -> str:
        return ctx.sheet.append_row(fields_to_row(datos))

    return StructuredTool.from_function(
        registrar_en_hoja,
        description=(
            "Registra una fila en la hoja de cálculo de la empresa. 'datos' es una lista de "
            "columnas, por ejemplo [{'campo': 'cliente', 'valor': 'Ana'}]."
        ),
    )


def _email(ctx: ToolContext) -> BaseTool:
    def enviar_correo(para: str, asunto: str, cuerpo: str) -> str:
        return ctx.mailer.send(para, asunto, cuerpo)

    return StructuredTool.from_function(
        enviar_correo,
        description="Envía un correo electrónico en nombre de la empresa.",
    )


_FACTORIES: dict[str, Callable[[ToolContext], BaseTool]] = {
    "buscar_documentos": _search,
    "registrar_en_hoja": _sheet,
    "enviar_correo": _email,
}


def build_tools(config: AgentConfig, ctx: ToolContext) -> list[BaseTool]:
    """Only the tools the config enables, in the config's order."""
    return [_FACTORIES[name](ctx) for name in config.tools]

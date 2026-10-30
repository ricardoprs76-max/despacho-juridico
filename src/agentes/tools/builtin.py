"""The built-in tools, wired to their backends for one company."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from agentes.config import AgentConfig
from agentes.integrations import Mailer, SheetBackend, mailer_from_env, sheet_from_env
from agentes.legal.plazos import CATALOGO, PlazoDesconocido, calcular_plazo
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


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_fecha(value: str) -> date | str:
    """A date, or a one-line Spanish error to hand back to the model."""
    text = value.strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if not 1900 <= parsed.year <= 2100:
            return f"Fecha fuera de rango: {text}."
        return parsed
    return f"Fecha no válida: {text}. Usa el formato DD/MM/AAAA."


# Built from the catalogue so the model sees the exact list of valid keys.
Actuacion = StrEnum("Actuacion", {key: key for key in sorted(CATALOGO)})  # type: ignore[misc]


class PlazoArgs(BaseModel):
    actuacion: Actuacion = Field(description="Actuación procesal.")
    fecha_notificacion: str = Field(description="Fecha de notificación, DD/MM/AAAA.")
    notificacion_electronica: bool = Field(
        default=False,
        description="True si se notificó por mensaje de datos (Ley 2213 de 2022).",
    )


def _plazo(ctx: ToolContext) -> BaseTool:
    def calcular(
        actuacion: str, fecha_notificacion: str, notificacion_electronica: bool = False
    ) -> str:
        fecha = parse_fecha(fecha_notificacion)
        if isinstance(fecha, str):
            return fecha
        try:
            return calcular_plazo(str(actuacion), fecha, notificacion_electronica).texto()
        except PlazoDesconocido as exc:
            return str(exc)

    options = "; ".join(f"{t.clave} = {t.nombre} ({t.dias} días)" for t in CATALOGO.values())
    return StructuredTool.from_function(
        calcular,
        name="calcular_plazo",
        args_schema=PlazoArgs,
        description=(
            "Calcula el vencimiento de un término procesal colombiano en días hábiles "
            "(CGP art. 118, festivos y vacancia judicial). Actuaciones: " + options + "."
        ),
    )


_FACTORIES: dict[str, Callable[[ToolContext], BaseTool]] = {
    "buscar_documentos": _search,
    "registrar_en_hoja": _sheet,
    "enviar_correo": _email,
    "calcular_plazo": _plazo,
}


def build_tools(config: AgentConfig, ctx: ToolContext) -> list[BaseTool]:
    """Only the tools the config enables, in the config's order."""
    return [_FACTORIES[name](ctx) for name in config.tools]

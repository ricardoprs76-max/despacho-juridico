"""Spanish, one-line descriptions of pydantic validation errors (config, tools, API)."""

from collections.abc import Sequence
from typing import Any

from pydantic_core import ErrorDetails

_MESSAGES: dict[str, str] = {
    "missing": "falta este campo",
    "extra_forbidden": "campo no permitido",
    "literal_error": "valor no permitido (opciones: {expected})",
    "enum": "valor no permitido (opciones: {expected})",
    "less_than_equal": "debe ser menor o igual a {le}",
    "greater_than_equal": "debe ser mayor o igual a {ge}",
    "string_pattern_mismatch": "formato no válido (usa solo minúsculas, números y guiones)",
    "string_too_short": "debe tener al menos {min_length} caracteres",
    "string_too_long": "debe tener como máximo {max_length} caracteres",
    "string_type": "debe ser un texto",
    "bool_parsing": "debe ser true o false",
    "bool_type": "debe ser true o false",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "list_type": "debe ser una lista",
    "float_parsing": "debe ser un número",
    "float_type": "debe ser un número",
    "dict_type": "debe ser un grupo de campos",
    "model_attributes_type": "debe ser un grupo de campos",
}


def spanish_message(error: ErrorDetails) -> str:
    """Translate one pydantic error to Spanish, falling back to pydantic's own text."""
    ctx: dict[str, Any] = dict(error.get("ctx") or {})
    if error["type"] == "value_error" and "error" in ctx:
        return str(ctx["error"])
    if error["type"] == "string_too_short" and ctx.get("min_length") == 1:
        return "no puede estar vacío"
    if isinstance(ctx.get("expected"), str):
        # pydantic lists options as "'a', 'b' or 'c'".
        ctx["expected"] = ctx["expected"].replace(" or ", " o ")
    template = _MESSAGES.get(error["type"])
    if template is None:
        return error["msg"]
    try:
        return template.format(**ctx)
    except KeyError:
        return error["msg"]


def field_name(error: ErrorDetails, skip: int = 0) -> str:
    """Dotted location of an error, without the first `skip` parts (e.g. "body")."""
    parts = [str(part) for part in error["loc"][skip:]]
    return ".".join(parts) or "(raíz)"


def describe(errors: Sequence[ErrorDetails], skip: int = 0) -> str:
    """'campo: mensaje; otro: mensaje' for every error, in order, without duplicates."""
    seen: dict[str, None] = {}
    for error in errors:
        seen[f"{field_name(error, skip)}: {spanish_message(error)}"] = None
    return "; ".join(seen)

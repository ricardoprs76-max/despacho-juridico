"""Load and validate an AgentConfig from a YAML file."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from agentes.config.schema import AgentConfig


class ConfigError(Exception):
    """A configuration file could not be loaded; the message is user-facing Spanish."""


_MESSAGES: dict[str, str] = {
    "missing": "falta este campo",
    "extra_forbidden": "campo no permitido",
    "literal_error": "valor no permitido (opciones: {expected})",
    "less_than_equal": "debe ser menor o igual a {le}",
    "greater_than_equal": "debe ser mayor o igual a {ge}",
    "string_pattern_mismatch": "formato no válido (usa solo minúsculas, números y guiones)",
    "string_type": "debe ser un texto",
    "list_type": "debe ser una lista",
    "float_parsing": "debe ser un número",
    "float_type": "debe ser un número",
    "dict_type": "debe ser un grupo de campos",
}


def _spanish(error: ErrorDetails) -> str:
    """Translate a pydantic error to Spanish, falling back to pydantic's own text."""
    ctx: dict[str, Any] = dict(error.get("ctx") or {})
    if error["type"] == "value_error" and "error" in ctx:
        return str(ctx["error"])
    template = _MESSAGES.get(error["type"])
    if template is None:
        return error["msg"]
    try:
        return template.format(**ctx)
    except KeyError:
        return error["msg"]


def load_config(path: Path) -> AgentConfig:
    """Read a UTF-8 YAML file and return a validated AgentConfig.

    Raises ConfigError with a one-line Spanish message on any problem.
    """
    if not path.is_file():
        raise ConfigError(f"No se encontró el archivo de configuración: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError(
            f"El archivo {path} no está en UTF-8; guárdalo con codificación UTF-8."
        ) from exc
    except OSError as exc:
        raise ConfigError(f"No se pudo leer {path}: {exc.strerror or exc}") from exc
    except yaml.YAMLError as exc:
        detail = str(exc).replace("\n", " ")
        raise ConfigError(f"YAML inválido en {path}: {detail}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"YAML inválido en {path}: se esperaba un mapa de campos")

    try:
        config = AgentConfig.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first["loc"]) or "(raíz)"
        raise ConfigError(f"Campo inválido '{loc}' en {path}: {_spanish(first)}") from exc

    if config.knowledge_dir is not None and not config.knowledge_dir.is_absolute():
        config.knowledge_dir = (path.parent / config.knowledge_dir).resolve()
    return config

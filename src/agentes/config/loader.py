"""Load and validate an AgentConfig from a YAML file."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from agentes.config.schema import AgentConfig
from agentes.validation import field_name, spanish_message


class ConfigError(Exception):
    """A configuration file could not be loaded; the message is user-facing Spanish."""


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
        raise ConfigError(
            f"Campo inválido '{field_name(first)}' en {path}: {spanish_message(first)}"
        ) from exc

    if config.knowledge_dir is not None and not config.knowledge_dir.is_absolute():
        config.knowledge_dir = (path.parent / config.knowledge_dir).resolve()
    return config

from pathlib import Path

import pytest

from agentes.config import AgentConfig, ConfigError, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "configs" / "ejemplo.yaml"

MINIMAL = """\
id: prueba
company_name: Empresa de Prueba
sector: pruebas
tone: amable
"""


def write(tmp_path: Path, text: str, name: str = "c.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_example_config() -> None:
    config = load_config(EXAMPLE)
    assert config.company_name == "Ferretería El Tornillo"
    assert len(config.rules) == 3


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ConfigError, match="No se encontró el archivo de configuración"):
        load_config(missing)


def test_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    path = write(tmp_path, "id: [sin cerrar\n")
    with pytest.raises(ConfigError, match="YAML inválido"):
        load_config(path)


def test_non_mapping_yaml_raises_config_error(tmp_path: Path) -> None:
    path = write(tmp_path, "- solo\n- una lista\n")
    with pytest.raises(ConfigError, match="YAML inválido"):
        load_config(path)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, MINIMAL + "color_favorito: azul\n")
    with pytest.raises(ConfigError, match="Campo inválido 'color_favorito'"):
        load_config(path)


def test_bad_id_slug_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, MINIMAL.replace("id: prueba", "id: Con Espacios"))
    with pytest.raises(ConfigError, match="Campo inválido 'id'"):
        load_config(path)


def test_confirm_tools_must_be_subset(tmp_path: Path) -> None:
    path = write(tmp_path, MINIMAL + "tools: [buscar_documentos]\nconfirm_tools: [enviar_correo]\n")
    with pytest.raises(ConfigError, match="enviar_correo"):
        load_config(path)


def test_relative_knowledge_dir_resolved(tmp_path: Path) -> None:
    path = write(tmp_path, MINIMAL + "knowledge_dir: docs\n")
    config = load_config(path)
    assert config.knowledge_dir == (tmp_path / "docs").resolve()


def test_system_prompt_contains_rules_and_no_invent_line() -> None:
    config = AgentConfig(
        id="x",
        company_name="Clínica Sol",
        sector="salud",
        tone="profesional",
        rules=["No dar diagnósticos", "Horario: 8 a 5"],
    )
    prompt = config.system_prompt()
    assert "Clínica Sol" in prompt
    assert "salud" in prompt
    assert "- No dar diagnósticos" in prompt
    assert "- Horario: 8 a 5" in prompt
    assert "Si no sabes la respuesta, dilo claramente; nunca inventes datos." in prompt


def test_accents_round_trip(tmp_path: Path) -> None:
    tone = "cálido y cercano, ¿en qué te ayudo?"
    path = write(tmp_path, MINIMAL.replace("tone: amable", f'tone: "{tone}"'))
    assert tone in load_config(path).system_prompt()


def test_non_utf8_file_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "ansi.yaml"
    path.write_bytes(MINIMAL.replace("amable", "Ñandú").encode("cp1252"))
    with pytest.raises(ConfigError, match="no está en UTF-8"):
        load_config(path)


@pytest.mark.parametrize(
    ("yaml_text", "expected"),
    [
        (MINIMAL.replace("tone: amable\n", ""), "Campo inválido 'tone' en .*: falta este campo"),
        (MINIMAL + "otro: 1\n", "Campo inválido 'otro' en .*: campo no permitido"),
        (MINIMAL + "model:\n  provider: llama\n", "valor no permitido"),
        (MINIMAL + "model:\n  temperature: 5\n", "debe ser menor o igual a 1"),
    ],
)
def test_validation_messages_in_spanish(tmp_path: Path, yaml_text: str, expected: str) -> None:
    path = write(tmp_path, yaml_text)
    with pytest.raises(ConfigError, match=expected):
        load_config(path)


def test_unknown_tool_name_rejected_in_config(tmp_path: Path) -> None:
    path = write(tmp_path, MINIMAL + "tools: [buscar_documentos, volar]\n")
    with pytest.raises(ConfigError, match="Herramienta desconocida: volar"):
        load_config(path)

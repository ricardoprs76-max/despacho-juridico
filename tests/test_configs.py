"""Every shipped sector config must load, index its documents cleanly and answer."""

from pathlib import Path

import pytest

from agentes.config import load_config
from agentes.tools import build_context

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
ALL = sorted(CONFIGS.glob("*.yaml"))


def test_exactly_three_configs() -> None:
    assert [p.name for p in ALL] == ["clinica.yaml", "despacho-juridico.yaml", "tienda.yaml"]


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.stem)
def test_config_loads(path: Path) -> None:
    config = load_config(path)
    assert config.id == path.stem
    assert config.knowledge_dir is not None


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.stem)
def test_knowledge_has_no_warnings(path: Path, tmp_path: Path) -> None:
    assert build_context(load_config(path), tmp_path, env={}).warnings == ()


@pytest.mark.parametrize(
    ("name", "question", "source"),
    [
        ("tienda", "¿hacen domicilios?", "domicilios.md"),
        ("despacho-juridico", "¿cuánto cuesta la consulta?", "servicios-y-tarifas.md"),
        (
            "despacho-juridico",
            "¿qué pasa si incumplo el contrato de arriendo?",
            "modelo-contrato-arrendamiento.md",
        ),
        ("clinica", "¿cómo me preparo para el examen de sangre?", "preparacion-examenes.md"),
        ("clinica", "¿puedo cancelar mi cita?", "cancelaciones.md"),
    ],
)
def test_typical_question_finds_document(
    name: str, question: str, source: str, tmp_path: Path
) -> None:
    ctx = build_context(load_config(CONFIGS / f"{name}.yaml"), tmp_path, env={})
    hits = ctx.knowledge.search(question)
    assert hits, question
    assert hits[0].chunk.source == source


def test_despacho_enables_calcular_plazo() -> None:
    config = load_config(CONFIGS / "despacho-juridico.yaml")
    assert "calcular_plazo" in config.tools
    assert set(config.confirm_tools) == {"registrar_en_hoja", "enviar_correo"}


def test_clinica_rules_forbid_diagnosis() -> None:
    prompt = load_config(CONFIGS / "clinica.yaml").system_prompt()
    assert "diagnóstic" in prompt
    assert "123" in prompt


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.stem)
def test_side_effect_tools_need_confirmation(path: Path) -> None:
    config = load_config(path)
    for tool in ("registrar_en_hoja", "enviar_correo"):
        if tool in config.tools:
            assert tool in config.confirm_tools


def test_contract_model_is_marked_as_practice_material() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "data/demo/despacho/modelo-contrato-arrendamiento.md").read_text(
        encoding="utf-8"
    )
    first_lines = "\n".join(text.splitlines()[:5])
    assert "no usar como modelo" in first_lines.lower()
    assert "cláusulas problemáticas" in first_lines.lower()

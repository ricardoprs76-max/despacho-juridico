import email
from email import policy
from pathlib import Path

import pytest

from agentes.config import AgentConfig
from agentes.tools import SIDE_EFFECT_TOOLS, TOOL_NAMES, build_context, build_tools


def config(tools: list[str], knowledge_dir: Path | None = None) -> AgentConfig:
    return AgentConfig(
        id="t",
        company_name="Tienda",
        sector="ventas",
        tone="amable",
        tools=tools,
        knowledge_dir=knowledge_dir,
    )


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "horarios.md").write_text("El horario es de 8 a 6.", encoding="utf-8")
    return folder


def test_names() -> None:
    assert {"buscar_documentos", "registrar_en_hoja", "enviar_correo"} == TOOL_NAMES
    assert {"registrar_en_hoja", "enviar_correo"} == SIDE_EFFECT_TOOLS


def test_only_enabled_tools_built_in_config_order(tmp_path: Path, knowledge: Path) -> None:
    cfg = config(["enviar_correo", "buscar_documentos"], knowledge)
    tools = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    assert [t.name for t in tools] == ["enviar_correo", "buscar_documentos"]
    assert all(t.description for t in tools)


def test_search_tool_returns_cited_text(tmp_path: Path, knowledge: Path) -> None:
    cfg = config(["buscar_documentos"], knowledge)
    [search] = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    result = search.invoke({"consulta": "horario"})
    assert "El horario es de 8 a 6." in result
    assert "(Fuente: horarios.md)" in result


def test_sheet_tool_appends_row(tmp_path: Path) -> None:
    cfg = config(["registrar_en_hoja"])
    [sheet] = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    assert sheet.invoke({"datos": {"cliente": "Ana"}}) == "Fila registrada en hoja.csv."
    assert "Ana" in (tmp_path / "hoja.csv").read_text(encoding="utf-8-sig")


def test_email_tool_writes_outbox(tmp_path: Path) -> None:
    cfg = config(["enviar_correo"])
    [mail] = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    result = mail.invoke({"para": "a@b.co", "asunto": "Hola", "cuerpo": "¿Qué tal?"})
    assert result.startswith("Correo guardado en la bandeja de salida:")
    [file] = list((tmp_path / "bandeja_salida").glob("*.eml"))
    parsed = email.message_from_bytes(file.read_bytes(), policy=policy.default)
    assert parsed["Subject"] == "Hola"


def test_context_skips_knowledge_when_search_disabled(tmp_path: Path) -> None:
    cfg = config(["enviar_correo"], tmp_path / "no-existe")
    ctx = build_context(cfg, tmp_path, env={})
    assert ctx.warnings == ()
    assert ctx.knowledge.search("lo que sea") == []


def test_context_reports_knowledge_warnings(tmp_path: Path) -> None:
    cfg = config(["buscar_documentos"], tmp_path / "no-existe")
    ctx = build_context(cfg, tmp_path, env={})
    assert ctx.warnings == (f"La carpeta de documentos no existe: {tmp_path / 'no-existe'}",)


def test_search_enabled_without_knowledge_dir_warns(tmp_path: Path) -> None:
    ctx = build_context(config(["buscar_documentos"]), tmp_path, env={})
    assert ctx.warnings == ("buscar_documentos está activa pero no hay knowledge_dir configurado.",)

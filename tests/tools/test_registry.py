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
    assert {
        "buscar_documentos",
        "registrar_en_hoja",
        "enviar_correo",
        "calcular_plazo",
    } == TOOL_NAMES
    assert {"registrar_en_hoja", "enviar_correo"} == SIDE_EFFECT_TOOLS


def test_only_enabled_tools_built_in_config_order(tmp_path: Path, knowledge: Path) -> None:
    cfg = config(["enviar_correo", "buscar_documentos"], knowledge)
    cfg = cfg.model_copy(update={"confirm_tools": ["enviar_correo"]})
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
    datos = [{"campo": "cliente", "valor": "Ana"}]
    assert sheet.invoke({"datos": datos}) == "Fila registrada en hoja.csv."
    assert "Ana" in (tmp_path / "hoja.csv").read_text(encoding="utf-8-sig")


def test_email_tool_writes_outbox(tmp_path: Path) -> None:
    cfg = config(["enviar_correo"]).model_copy(update={"confirm_tools": ["enviar_correo"]})
    [mail] = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    result = mail.invoke({"para": "a@b.co", "asunto": "Hola", "cuerpo": "¿Qué tal?"})
    assert result.startswith("Correo guardado en la bandeja de salida:")
    [file] = list((tmp_path / "bandeja_salida").glob("*.eml"))
    parsed = email.message_from_bytes(file.read_bytes(), policy=policy.default)
    assert parsed["Subject"] == "Hola"


def test_context_skips_knowledge_when_search_disabled(tmp_path: Path) -> None:
    cfg = config(["enviar_correo"], tmp_path / "no-existe")
    cfg = cfg.model_copy(update={"confirm_tools": ["enviar_correo"]})
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


def _objects_without_properties(schema: object) -> list[object]:
    found: list[object] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and not schema.get("properties"):
            found.append(schema)
        for value in schema.values():
            found += _objects_without_properties(value)
    elif isinstance(schema, list):
        for item in schema:
            found += _objects_without_properties(item)
    return found


def test_tool_schemas_have_no_open_objects(tmp_path: Path, knowledge: Path) -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    cfg = config(["buscar_documentos", "registrar_en_hoja", "enviar_correo"], knowledge)
    for tool in build_tools(cfg, build_context(cfg, tmp_path, env={})):
        schema = convert_to_openai_tool(tool)["function"]["parameters"]
        assert _objects_without_properties(schema) == [], tool.name


def test_side_effect_tool_without_confirmation_warns(tmp_path: Path) -> None:
    cfg = config(["enviar_correo"])
    ctx = build_context(cfg, tmp_path, env={})
    assert ctx.warnings == ("enviar_correo se ejecutará sin pedir confirmación.",)


def _plazo_tool(tmp_path: Path):  # type: ignore[no-untyped-def]
    cfg = config(["calcular_plazo"])
    [tool] = build_tools(cfg, build_context(cfg, tmp_path, env={}))
    return tool


def test_plazo_tool_returns_text(tmp_path: Path) -> None:
    text = _plazo_tool(tmp_path).invoke(
        {"actuacion": "reposicion", "fecha_notificacion": "02/03/2026"}
    )
    assert "Vence el 05/03/2026 (jueves)." in text
    assert text.endswith("extraordinario del despacho.")


@pytest.mark.parametrize("value", ["2026-03-02", "02/03/2026", "02-03-2026", "2/3/2026"])
def test_plazo_tool_accepts_date_formats(tmp_path: Path, value: str) -> None:
    text = _plazo_tool(tmp_path).invoke({"actuacion": "reposicion", "fecha_notificacion": value})
    assert "Notificación: 02/03/2026." in text


def test_plazo_tool_bad_date_message(tmp_path: Path) -> None:
    text = _plazo_tool(tmp_path).invoke(
        {"actuacion": "reposicion", "fecha_notificacion": "31/02/2026"}
    )
    assert text == "Fecha no válida: 31/02/2026. Usa el formato DD/MM/AAAA."


def test_plazo_tool_out_of_range_message(tmp_path: Path) -> None:
    text = _plazo_tool(tmp_path).invoke(
        {"actuacion": "reposicion", "fecha_notificacion": "01/01/1800"}
    )
    assert text == "Fecha fuera de rango: 01/01/1800 (se admiten fechas entre 2012 y 2100)."


def test_plazo_tool_electronic(tmp_path: Path) -> None:
    text = _plazo_tool(tmp_path).invoke(
        {
            "actuacion": "excepciones_ejecutivo",
            "fecha_notificacion": "02/03/2026",
            "notificacion_electronica": True,
        }
    )
    assert "Vence el 18/03/2026 (miércoles)." in text


def test_plazo_tool_rejects_dates_before_cgp(tmp_path: Path) -> None:
    text = _plazo_tool(tmp_path).invoke(
        {"actuacion": "reposicion", "fecha_notificacion": "01/01/1990"}
    )
    assert text == "Fecha fuera de rango: 01/01/1990 (se admiten fechas entre 2012 y 2100)."


def test_plazo_param_says_personal_notification(tmp_path: Path) -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    params = convert_to_openai_tool(_plazo_tool(tmp_path))["function"]["parameters"]
    description = params["properties"]["notificacion_electronica"]["description"]
    assert "personal" in description
    assert "estado" in description


def test_plazo_schema_enumerates_actuaciones(tmp_path: Path) -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    from agentes.legal.plazos import CATALOGO

    params = convert_to_openai_tool(_plazo_tool(tmp_path))["function"]["parameters"]
    assert sorted(params["properties"]["actuacion"]["enum"]) == sorted(CATALOGO)
    assert params["required"] == ["actuacion", "fecha_notificacion"]


def test_plazo_is_read_only() -> None:
    assert "calcular_plazo" in TOOL_NAMES
    assert "calcular_plazo" not in SIDE_EFFECT_TOOLS

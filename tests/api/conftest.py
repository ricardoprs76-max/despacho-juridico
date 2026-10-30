"""Fixtures: a TestClient around an Agent driven by a scripted model."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentes.agent import Agent
from agentes.api import create_app
from agentes.config import AgentConfig
from tests.conftest import RecordingChatModel, selection_for

EMAIL_ARGS = {"para": "ana@ejemplo.com", "asunto": "Cotización", "cuerpo": "Adjunto precios."}

MakeClient = Callable[..., TestClient]


def make_config(tmp_path: Path) -> AgentConfig:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "horarios.md").write_text("El horario es de 8 a 6.", encoding="utf-8")
    return AgentConfig(
        id="tienda",
        company_name="Ferretería El Tornillo",
        sector="ferretería y materiales de construcción",
        tone="amable",
        tools=["buscar_documentos", "registrar_en_hoja", "enviar_correo"],
        confirm_tools=["registrar_en_hoja", "enviar_correo"],
        knowledge_dir=docs,
    )


def outbox(tmp_path: Path) -> list[Path]:
    return list((tmp_path / "data" / "bandeja_salida").glob("*.eml"))


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[MakeClient]:
    agents: list[Agent] = []

    def factory(
        replies: list[Any], api_key: str | None = None, config: AgentConfig | None = None
    ) -> TestClient:
        agent = Agent(
            config or make_config(tmp_path),
            selection_for(RecordingChatModel(replies=replies)),
            db_path=tmp_path / "data" / "m.sqlite",
            env={},
        )
        agents.append(agent)
        return TestClient(create_app(agent, api_key=api_key))

    yield factory
    for agent in agents:
        agent.close()

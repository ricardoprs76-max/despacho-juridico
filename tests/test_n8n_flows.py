"""The importable n8n flow templates: valid, safe, and talking to the agent correctly."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from agentes.api.schemas import THREAD_PATTERN

FLOWS_DIR = Path(__file__).resolve().parents[1] / "integrations" / "n8n" / "flows"
FLOW_FILES = sorted(FLOWS_DIR.glob("*.json"))
AGENT_NODE = "CUSTOM.agentesIa"
# The JS expression every flow uses, as ('<prefix>-' + source).replace(...).slice(0, 64).
THREAD_EXPR = re.compile(
    r"\('(?P<prefix>[a-z]+)-' \+ .+?\)\.replace\(/\[\^A-Za-z0-9_-\]/g, '-'\)\.slice\(0, 64\)"
)


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def agent_nodes(flow: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in flow["nodes"] if n["type"] == AGENT_NODE]


def sanitize(prefix: str, source: str) -> str:
    """Python twin of the flows' thread-id expression."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{prefix}-{source}")[:64]


def test_expected_flows_exist() -> None:
    assert [p.name for p in FLOW_FILES] == [
        "aprobar-accion.json",
        "correo-a-agente.json",
        "whatsapp-a-agente.json",
    ]


@pytest.mark.parametrize("path", FLOW_FILES, ids=lambda p: p.name)
def test_flow_structure(path: Path) -> None:
    flow = load(path)
    assert flow["name"]
    names = {n["name"] for n in flow["nodes"]}
    assert len(names) == len(flow["nodes"]), "node names must be unique"
    for source, outputs in flow["connections"].items():
        assert source in names, source
        for branch in outputs["main"]:
            for link in branch:
                assert link["node"] in names, link
    assert agent_nodes(flow), "every flow calls the agent"
    rebuilt = any("langchain" in n["type"] for n in flow["nodes"])
    assert not rebuilt, "the agent is not rebuilt in n8n"


@pytest.mark.parametrize("path", FLOW_FILES, ids=lambda p: p.name)
def test_flow_has_no_secrets(path: Path) -> None:
    flow = load(path)
    for node in flow["nodes"]:
        for cred in node.get("credentials", {}).values():
            assert "id" not in cred, f"{node['name']} embeds a credential id"
    text = path.read_text(encoding="utf-8").lower()
    for word in ("apikey", "password", "secret", "token"):
        assert f'"{word}"' not in text


@pytest.mark.parametrize("path", FLOW_FILES, ids=lambda p: p.name)
def test_every_agent_call_has_a_valid_thread(path: Path) -> None:
    for node in agent_nodes(load(path)):
        thread = node["parameters"]["threadId"]
        if node["parameters"].get("operation") == "confirm":
            assert thread.startswith("={{"), "confirm takes the thread from the request"
            continue
        match = THREAD_EXPR.search(thread)
        assert match, thread
        for source in ("ana.perez+ventas@ejemplo.com", "+57 300 123 4567", "x" * 200):
            assert re.fullmatch(THREAD_PATTERN, sanitize(match["prefix"], source))


@pytest.mark.parametrize("name", ["correo-a-agente.json", "whatsapp-a-agente.json"])
def test_pending_branch_is_handled(name: str) -> None:
    flow = load(FLOWS_DIR / name)
    [check] = [n for n in flow["nodes"] if n["type"] == "n8n-nodes-base.if"]
    assert "pending" in json.dumps(check["parameters"])
    true_branch, false_branch = flow["connections"][check["name"]]["main"]
    assert true_branch and false_branch, "both outcomes go somewhere"
    pending_text = json.dumps(flow, ensure_ascii=False)
    assert "pendiente de aprobación" in pending_text.lower()


def test_approval_flow_confirms_from_the_link() -> None:
    flow = load(FLOWS_DIR / "aprobar-accion.json")
    [webhook] = [n for n in flow["nodes"] if n["type"] == "n8n-nodes-base.webhook"]
    assert webhook["parameters"]["path"] == "aprobar"
    [agent] = agent_nodes(flow)
    assert agent["parameters"]["operation"] == "confirm"
    assert "conversacion" in agent["parameters"]["threadId"]
    assert "aprobar" in str(agent["parameters"]["approved"])


def test_sanitize_examples() -> None:
    email = sanitize("correo", "ana.perez+ventas@ejemplo.com")
    assert email == "correo-ana-perez-ventas-ejemplo-com"
    assert sanitize("wa", "+57 300 123 4567") == "wa--57-300-123-4567"

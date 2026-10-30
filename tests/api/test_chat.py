import re
import threading
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from tests.api.conftest import EMAIL_ARGS, MakeClient, outbox


def email_call() -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "enviar_correo", "args": EMAIL_ARGS, "id": "c1"}])


def test_health_reports_company_and_mode(make_client: MakeClient) -> None:
    body = make_client([]).get("/health").json()
    assert body == {
        "status": "ok",
        "company": "Ferretería El Tornillo",
        "sector": "ferretería y materiales de construcción",
        "demo": False,
        "provider": "test",
        "model": "recording",
        "auth": False,
    }


def test_chat_new_thread_then_continue(make_client: MakeClient) -> None:
    client = make_client(["Hola, ¿en qué te ayudo?", "Abrimos a las 8."])
    first = client.post("/chat", json={"message": "hola"}).json()
    assert first["reply"] == "Hola, ¿en qué te ayudo?"
    assert first["pending"] is None
    assert re.fullmatch(r"[0-9a-f]{32}", first["thread_id"])
    second = client.post("/chat", json={"message": "¿horario?", "thread_id": first["thread_id"]})
    assert second.json()["reply"] == "Abrimos a las 8."
    hist = client.get(f"/chat/{first['thread_id']}").json()
    assert hist["pending"] is None
    assert hist["messages"] == [
        {"role": "user", "text": "hola"},
        {"role": "assistant", "text": "Hola, ¿en qué te ayudo?"},
        {"role": "user", "text": "¿horario?"},
        {"role": "assistant", "text": "Abrimos a las 8."},
    ]


def test_unknown_thread_history_is_empty(make_client: MakeClient) -> None:
    body = make_client([]).get("/chat/nuevo").json()
    assert body == {"thread_id": "nuevo", "messages": [], "pending": None}


def test_side_effect_waits_for_confirmation(make_client: MakeClient, tmp_path: Path) -> None:
    client = make_client([email_call(), "Listo, correo enviado."])
    r = client.post("/chat", json={"message": "envía la cotización", "thread_id": "t1"}).json()
    assert r["reply"] == ""
    assert r["pending"]["tool"] == "enviar_correo"
    assert r["pending"]["args"] == EMAIL_ARGS
    assert r["pending"]["description"].startswith("Enviar correo a ana@ejemplo.com")
    assert outbox(tmp_path) == []
    assert client.get("/chat/t1").json()["pending"]["tool"] == "enviar_correo"
    done = client.post("/chat/t1/confirm", json={"approved": True}).json()
    assert done == {"thread_id": "t1", "reply": "Listo, correo enviado.", "pending": None}
    assert len(outbox(tmp_path)) == 1


def test_rejected_action_does_not_run(make_client: MakeClient, tmp_path: Path) -> None:
    client = make_client([email_call(), "Entendido, no lo envío."])
    client.post("/chat", json={"message": "envía", "thread_id": "t1"})
    done = client.post("/chat/t1/confirm", json={"approved": False}).json()
    assert done["reply"] == "Entendido, no lo envío."
    assert outbox(tmp_path) == []


def test_second_confirm_is_409(make_client: MakeClient) -> None:
    client = make_client([email_call(), "Listo."])
    client.post("/chat", json={"message": "envía", "thread_id": "t1"})
    assert client.post("/chat/t1/confirm", json={"approved": True}).status_code == 200
    again = client.post("/chat/t1/confirm", json={"approved": True})
    assert again.status_code == 409
    assert again.json() == {"detail": "No hay ninguna acción pendiente de confirmar."}


def test_message_while_pending_is_409(make_client: MakeClient) -> None:
    client = make_client([email_call()])
    client.post("/chat", json={"message": "envía", "thread_id": "t1"})
    r = client.post("/chat", json={"message": "otra cosa", "thread_id": "t1"})
    assert r.status_code == 409
    assert r.json() == {"detail": "Primero confirma o cancela la acción pendiente."}


def test_concurrent_confirms_run_action_once(make_client: MakeClient, tmp_path: Path) -> None:
    client = make_client([email_call(), "Listo."])
    client.post("/chat", json={"message": "envía", "thread_id": "t1"})
    codes: list[int] = []
    start = threading.Barrier(2)

    def confirm() -> None:
        start.wait()
        codes.append(client.post("/chat/t1/confirm", json={"approved": True}).status_code)

    threads = [threading.Thread(target=confirm) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409]
    assert len(outbox(tmp_path)) == 1


def test_model_failure_is_502_and_thread_recovers(make_client: MakeClient) -> None:
    client = make_client([RuntimeError("cuota agotada"), "Ahora sí."])
    r = client.post("/chat", json={"message": "hola", "thread_id": "t1"})
    assert r.status_code == 502
    assert r.json() == {"detail": "No se pudo obtener respuesta del modelo: cuota agotada"}
    ok = client.post("/chat", json={"message": "hola", "thread_id": "t1"})
    assert ok.status_code == 200
    assert ok.json()["reply"] == "Ahora sí."
    assert len(client.get("/chat/t1").json()["messages"]) == 2


@pytest.mark.parametrize("thread", ["../x", "a" * 65, "con espacio", ""])
def test_bad_thread_id_is_422(make_client: MakeClient, thread: str) -> None:
    r = make_client(["x"]).post("/chat", json={"message": "hola", "thread_id": thread})
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/chat/con%20espacio", "/chat/" + "a" * 65])
def test_bad_thread_in_path_is_422(make_client: MakeClient, path: str) -> None:
    assert make_client([]).get(path).status_code == 422


@pytest.mark.parametrize("message", ["", "   ", "x" * 4001])
def test_bad_message_is_422(make_client: MakeClient, message: str) -> None:
    r = make_client(["x"]).post("/chat", json={"message": message})
    assert r.status_code == 422


def test_api_key_required_when_set(make_client: MakeClient) -> None:
    client = make_client(["Hola."], api_key="s3creta")
    calls: list[tuple[str, str, dict[str, Any] | None]] = [
        ("post", "/chat", {"message": "hola", "thread_id": "t1"}),
        ("post", "/chat/t1/confirm", {"approved": True}),
        ("get", "/chat/t1", None),
    ]
    seen: list[str] = []
    for method, path, body in calls:
        for headers in ({}, {"X-API-Key": "mala"}):
            r = client.request(method, path, json=body, headers=headers)
            assert r.status_code == 401, (path, headers)
            assert r.json() == {"detail": "Clave de API inválida o ausente."}
            seen.append(r.text)
    ok = client.post(
        "/chat", json={"message": "hola", "thread_id": "t1"}, headers={"X-API-Key": "s3creta"}
    )
    assert ok.status_code == 200
    seen.append(ok.text)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["auth"] is True
    seen.append(health.text)
    assert client.get("/docs").status_code == 200
    assert all("s3creta" not in text for text in seen)

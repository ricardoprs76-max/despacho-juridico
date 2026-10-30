import pytest
from langchain_core.messages import AIMessage

from tests.api.conftest import EMAIL_ARGS, MakeClient

KEY = {"X-API-Key": "s3creta"}


def email_call(call_id: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "enviar_correo", "args": EMAIL_ARGS, "id": call_id}])


def test_audit_lists_confirmed_and_rejected(make_client: MakeClient) -> None:
    client = make_client(
        [email_call("c1"), "Enviado.", email_call("c2"), "Cancelado.", email_call("c3"), "Ok."]
    )
    for thread, approved in (("t1", True), ("t1", False), ("t2", True)):
        client.post("/chat", json={"message": "envía", "thread_id": thread})
        client.post(f"/chat/{thread}/confirm", json={"approved": approved})
    entries = client.get("/audit", params={"thread_id": "t1"}).json()
    assert [e["status"] for e in entries] == ["rejected", "executed"]
    assert {e["thread_id"] for e in entries} == {"t1"}
    assert entries[0]["tool"] == "enviar_correo"
    assert entries[0]["args"] == EMAIL_ARGS
    assert len(client.get("/audit").json()) == 3
    assert len(client.get("/audit", params={"limit": 1}).json()) == 1


@pytest.mark.parametrize("limit", [0, 501])
def test_audit_limit_bounds(make_client: MakeClient, limit: int) -> None:
    assert make_client([]).get("/audit", params={"limit": limit}).status_code == 422


def test_audit_bad_thread_is_422(make_client: MakeClient) -> None:
    assert make_client([]).get("/audit", params={"thread_id": "../x"}).status_code == 422


def test_audit_requires_key(make_client: MakeClient) -> None:
    client = make_client([], api_key="s3creta")
    assert client.get("/audit").status_code == 401
    assert client.get("/audit", headers={"X-API-Key": "mala"}).status_code == 401
    ok = client.get("/audit", headers=KEY)
    assert ok.status_code == 200
    assert ok.json() == []

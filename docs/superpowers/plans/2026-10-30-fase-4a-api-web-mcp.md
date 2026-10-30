# Phase 4a — API, Web Demo and MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve one company's agent over HTTP (FastAPI, API-key auth, OpenAPI docs), give it a small Spanish web chat with on-screen confirmation of actions, and expose it as an MCP server, all without Docker.

**Architecture:** `agentes.api.create_app(agent, api_key)` builds a FastAPI app around an already-open `Agent` (the caller owns its lifetime), so tests inject an `Agent` built on the scripted `RecordingChatModel`. One `threading.Lock` serialises agent calls (SQLite + LangGraph checkpoints are not safe for concurrent turns on one thread). The web demo is static HTML/CSS/JS shipped inside the package and served by the same app at `/`. `agentes.mcp.build_mcp_server(agent)` wraps the same `Agent` with the official MCP SDK (stdio transport). New CLI commands: `agentes serve` and `agentes mcp`.

**Tech Stack:** Phase 1–3 stack + `fastapi`, `uvicorn`, `mcp` (official Python SDK, FastMCP high-level server); dev: `httpx` (for `fastapi.testclient`). Versions current on 2026-10-30: fastapi 0.162, uvicorn 0.54, mcp 2.3, httpx 0.28.

**Spec:** `docs/superpowers/specs/2026-10-30-agentes-ia-empresas-design.md` (Phase 4; 4b = n8n + Docker is a separate plan).

## Global Constraints

- All Phase 1–3 constraints apply: `python -m uv` (no `uv.exe` on PATH), ruff + `mypy --strict` + pytest green, `set -o pipefail` on any piped check, English code/identifiers/docstrings, Spanish user-facing text, UTF-8, LF line endings, author `Ricardo Porras <ricardoprs76@gmail.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `fase-4-api` from `main`.
- Tests never call real LLM APIs or the network; MCP tests run in-process.
- JSON field names in English (API audience); every `detail`/message string in Spanish.
- Safety rules from the spec stay true on every surface: side-effecting tools (`registrar_en_hoja`, `enviar_correo`) only run after an explicit yes; every tool call is written to the audit log.
- README must not stress "made with AI".
- Assistant's calls (owner may override): one company per server process; no auth when `AGENTES_API_KEY` is unset BUT then the server refuses to bind to anything other than `127.0.0.1`/`localhost`; MCP client (agent consuming external MCP tools) is deferred to a later phase; MCP transport = stdio only.

## Review Focus

1. Double-click on "Enviar" or "Confirmar" (two identical requests at once) → actions run once; the second request gets 409 with a Spanish reason, never a 500 (Task 1 and Task 2 tests).
2. Model failure mid-conversation (invalid key, rate limit) → 502 with Spanish detail, and the next message on the same conversation works (Task 1 test).
3. Missing or wrong `X-API-Key` → 401 on every `/chat*` and `/audit` route, while `/health`, `/` and `/docs` stay reachable; the key never appears in any response (Task 1 test).
4. Hostile or odd `thread_id` (`../x`, 65 chars, spaces) and empty / 4001-char messages → 422, not a stored conversation (Task 1 test).
5. Agent text containing HTML (`<img src=x onerror=alert(1)>`) is shown as text in the web demo, never executed (Task 3 test).

---

### Task 1: FastAPI app — health, chat, confirm, history, auth

**Files:**
- Modify: `pyproject.toml` (deps `fastapi>=0.115`, `uvicorn>=0.30`; dev `httpx>=0.27`), `uv.lock`
- Create: `src/agentes/api/__init__.py`, `src/agentes/api/app.py`, `src/agentes/api/schemas.py`
- Test: `tests/api/__init__.py`, `tests/api/conftest.py`, `tests/api/test_chat.py`

**Interfaces:**
- Consumes: `Agent.ask/confirm/pending/history/is_demo/selection/config`, `AgentError`, `PendingAction` (`src/agentes/agent.py`); `RecordingChatModel`, `selection_for`, `example_config` (`tests/conftest.py`).
- Produces:
  - `create_app(agent: Agent, api_key: str | None = None) -> FastAPI` in `agentes.api` (re-exported from `agentes/api/__init__.py`).
  - Header `X-API-Key`; constant `API_KEY_HEADER = "X-API-Key"`.
  - Schemas (pydantic, `schemas.py`): `ChatRequest(message: str [1..4000 chars, stripped], thread_id: str | None [pattern ^[A-Za-z0-9_-]{1,64}$])`, `ConfirmRequest(approved: bool)`, `PendingOut(tool: str, args: dict[str, Any], description: str)`, `ChatResponse(thread_id: str, reply: str, pending: PendingOut | None)`, `MessageOut(role: Literal["user","assistant"], text: str)`, `HistoryResponse(thread_id: str, messages: list[MessageOut], pending: PendingOut | None)`, `HealthResponse(status: Literal["ok"], company: str, sector: str, demo: bool, provider: str, model: str, auth: bool)`.
  - Routes: `GET /health` (no auth) · `POST /chat` → `ChatResponse` (new `thread_id = uuid4().hex` when omitted) · `POST /chat/{thread_id}/confirm` → `ChatResponse` · `GET /chat/{thread_id}` → `HistoryResponse` (user messages and non-empty assistant texts only, oldest first; unknown thread → empty list, 200).
  - Error mapping: `ValueError` from `Agent` → 409 `{"detail": <its Spanish message>}`; `AgentError` → 502 `{"detail": "No se pudo obtener respuesta del modelo: <msg>"}`; bad key → 401 `{"detail": "Clave de API inválida o ausente."}`.
  - `app.state.agent_lock: threading.Lock` held around every `Agent` call (endpoints are plain `def`, run in FastAPI's threadpool).
  - Auth compares with `secrets.compare_digest`; when `api_key is None` no route needs a key.

- [ ] **Step 1: Branch and dependencies**

Run: `git checkout -b fase-4-api && python -m uv add "fastapi>=0.115" "uvicorn>=0.30" && python -m uv add --dev "httpx>=0.27"`
Expected: lock updated, `python -m uv run python -c "import fastapi, uvicorn"` exits 0.

- [ ] **Step 2: Write failing tests** in `tests/api/test_chat.py` (fixture in `tests/api/conftest.py`: `make_client(replies, api_key=None, config=example_config) -> TestClient` building `Agent(config, selection_for(RecordingChatModel(replies=replies)), db_path=tmp_path/"m.sqlite", data_dir=tmp_path)` and closing it on teardown):

```python
def test_health_reports_company_and_mode(make_client):
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


def test_chat_new_thread_then_continue(make_client):
    client = make_client(["Hola, ¿en qué te ayudo?", "Abrimos a las 7."])
    first = client.post("/chat", json={"message": "hola"}).json()
    assert first["reply"] == "Hola, ¿en qué te ayudo?" and first["pending"] is None
    assert re.fullmatch(r"[0-9a-f]{32}", first["thread_id"])
    second = client.post("/chat", json={"message": "¿horario?", "thread_id": first["thread_id"]})
    assert second.json()["reply"] == "Abrimos a las 7."
    hist = client.get(f"/chat/{first['thread_id']}").json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant", "user", "assistant"]


def test_side_effect_waits_for_confirmation(make_client, tmp_path):
    # model asks to send an email (AIMessage with tool_calls for enviar_correo), then answers
    ...  # reply 1 = tool call, reply 2 = "Listo, correo enviado."
    r = client.post("/chat", json={"message": "envía el correo", "thread_id": "t1"}).json()
    assert r["reply"] == "" and r["pending"]["tool"] == "enviar_correo"
    assert "Enviar correo a ana@example.com" in r["pending"]["description"]
    assert not (tmp_path / "bandeja_salida").exists() or not any(
        (tmp_path / "bandeja_salida").iterdir()
    )
    done = client.post("/chat/t1/confirm", json={"approved": True}).json()
    assert done == {"thread_id": "t1", "reply": "Listo, correo enviado.", "pending": None}


def test_second_confirm_is_409(
    make_client,
): ...  # after confirming, confirm again → 409, detail "No hay ninguna acción pendiente de confirmar."
def test_message_while_pending_is_409(
    make_client,
): ...  # detail "Primero confirma o cancela la acción pendiente."
def test_concurrent_confirms_run_action_once(
    make_client,
): ...  # two threads POST confirm at once → one 200, one 409; outbox has exactly 1 email
def test_model_failure_is_502_and_thread_recovers(
    make_client,
): ...  # replies [RuntimeError("cuota"), "Ahora sí."] → 502 detail contains "cuota"; next message → 200 "Ahora sí."
@pytest.mark.parametrize("thread", ["../x", "a" * 65, "con espacio"])
def test_bad_thread_id_is_422(make_client, thread): ...  # POST /chat with that thread_id → 422
@pytest.mark.parametrize("message", ["", "   ", "x" * 4001])
def test_bad_message_is_422(make_client, message): ...
def test_api_key_required_when_set(make_client):
    ...
    # api_key="s3creta": /chat, /chat/t/confirm, /chat/t, /audit without header → 401;
    # wrong header → 401; right header → not 401; /health → 200 with "auth": True;
    # "s3creta" not in any response text.
```

Use the outbox folder the existing email tests use (read `tests/integrations/test_email.py` for its name) instead of guessing `bandeja_salida`.

- [ ] **Step 3: Run** `python -m uv run pytest tests/api -q` → FAIL (`agentes.api` missing).
- [ ] **Step 4: Implement** `schemas.py` and `app.py` per the Interfaces block. Auth as a FastAPI dependency applied to the chat/audit routers. `/audit` route belongs to Task 2 — for this task's auth test, register it now as a stub that Task 2 completes, or let Task 2 add it and move the `/audit` line of the auth test there (pick the latter).
- [ ] **Step 5: Run** full suite + `ruff check .`, `ruff format --check .`, `mypy` → all green.
- [ ] **Step 6: Commit** `feat(api): add FastAPI service with chat, confirmation and API-key auth`.

### Task 2: Audit endpoint and `agentes serve`

**Files:**
- Modify: `src/agentes/api/app.py`, `src/agentes/api/schemas.py`, `src/agentes/cli.py`
- Test: `tests/api/test_audit.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `AuditLog.entries(thread_id, limit)`, `Agent.audit`; `create_app` from Task 1.
- Produces:
  - `AuditEntryOut(id: int, timestamp: datetime, thread_id: str, tool: str, args: dict[str, Any], status: Literal["executed","rejected","error"], result: str)`; `GET /audit?thread_id=&limit=` (auth; `limit` 1..500, default 50; newest first) → `list[AuditEntryOut]`.
  - CLI `agentes serve CONFIG [--host 127.0.0.1] [--port 8000] [--data .agentes]`: reads `AGENTES_API_KEY` from env/.env; runs `uvicorn.run(create_app(agent, key), host, port)` with the agent opened in a `with` block. Refuses to start (exit code 2, message `Sin AGENTES_API_KEY solo se permite --host 127.0.0.1 o localhost.`) when the key is empty and host is anything else. Prints the demo notice and warnings like `chat` does, plus `Abre http://<host>:<port> en el navegador.`

- [ ] **Step 1: Failing tests:** `test_audit_lists_confirmed_and_rejected` (one email approved, one rejected on thread `t1`, one on `t2` → `/audit?thread_id=t1` returns 2 entries, newest first, statuses `["rejected","executed"]`); `test_audit_limit_bounds` (`limit=0` and `limit=501` → 422); `test_audit_requires_key` (moved from Task 1); `test_serve_refuses_public_host_without_key` (CliRunner, `serve configs/tienda.yaml --host 0.0.0.0`, env without key → exit 2 and the message; `uvicorn.run` monkeypatched to fail the test if called); `test_serve_runs_uvicorn` (monkeypatch `uvicorn.run` to record host/port and the app's `/health` via TestClient → `company` matches).
- [ ] **Step 2: Run → FAIL. Step 3: Implement. Step 4: Full checks → green.**
- [ ] **Step 5: Commit** `feat(api): add audit endpoint and serve command`.

### Task 3: Web chat demo

**Files:**
- Create: `src/agentes/api/static/index.html`, `src/agentes/api/static/app.js`, `src/agentes/api/static/styles.css`
- Modify: `src/agentes/api/app.py` (mount `StaticFiles(directory=<package>/static, html=True)` at `/` AFTER the API routes), `pyproject.toml` only if hatch does not ship the static files (check with `python -m uv build` and listing the wheel)
- Test: `tests/api/test_web.py`

**Interfaces:**
- Consumes: the routes of Tasks 1–2 only (the page is a plain API client).
- Produces: a single Spanish page:
  - Header: company name and sector from `/health`; badge `Modo demo` when `demo` is true, otherwise `<provider> · <model>`.
  - Chat list + textarea; Enter sends, Shift+Enter new line; send button disabled while a request is in flight (prevents the double send).
  - Pending action card with the `description` and two buttons `Confirmar` / `Cancelar` (both disabled after the first click).
  - "Acciones registradas" panel reading `/audit?thread_id=<current>` after every turn.
  - Conversation id kept in `localStorage` (try/catch) and restored with `GET /chat/{id}`; button `Nueva conversación`.
  - When `/health` says `auth: true`: a key field; key kept in `sessionStorage` only; 401 shows `Clave de API inválida o ausente.`
  - Errors (409/502/network) shown inline in Spanish, chat stays usable.
  - All agent/user text inserted with `textContent` / `createTextNode` — no `innerHTML` with dynamic data. No external scripts or fonts (works offline).
  - Visual style: follow the `design-taste-frontend` skill for app screens; keep it one light page, readable at 360 px width.

- [ ] **Step 1: Failing tests:** `test_root_serves_page` (`GET /` → 200, `text/html`, contains `<title>` and `app.js`); `test_static_assets_served` (`/app.js`, `/styles.css` → 200); `test_page_does_not_need_key` (api_key set → `/` and `/app.js` still 200); `test_js_never_uses_innerhtml_with_data` (`"innerHTML" not in app.js` source and `"textContent"` in it); `test_api_routes_win_over_static` (`/health` still JSON after the mount).
- [ ] **Step 2: Run → FAIL. Step 3: Build the page. Step 4: Full checks → green.**
- [ ] **Step 5: Manual check:** `agentes serve configs/tienda.yaml` in demo mode; in a browser (playwright-cli skill) send a message, trigger an email confirmation, confirm, see it in "Acciones registradas"; screenshot at 1280 and 375 px; paste of `<img src=x onerror=alert(1)>` shows as text.
- [ ] **Step 6: Commit** `feat(web): add Spanish chat demo with on-screen confirmation`.

### Task 4: MCP server and `agentes mcp`

**Files:**
- Modify: `pyproject.toml` (dep `mcp>=2.0`), `uv.lock`, `src/agentes/agent.py`, `src/agentes/cli.py`
- Create: `src/agentes/mcp/__init__.py`, `src/agentes/mcp/server.py`
- Test: `tests/mcp/__init__.py`, `tests/mcp/test_server.py`, `tests/graph/test_agent.py` (run_tool tests)

**Interfaces:**
- Consumes: `Agent`, `SIDE_EFFECT_TOOLS`.
- Produces:
  - `Agent.tools: tuple[BaseTool, ...]` (the built tools, kept from `__init__`).
  - `Agent.run_tool(name: str, args: dict[str, Any], thread_id: str = "mcp") -> str`: runs one enabled read-only tool directly and records it in the audit log (status `executed` or `error`); raises `ValueError("La herramienta <name> no está disponible.")` when not enabled and `ValueError("<name> tiene efectos; pídela a través de preguntar para confirmarla.")` for side-effecting tools.
  - `build_mcp_server(agent: Agent) -> FastMCP` in `agentes.mcp` (server name = `agent.config.company_name`). Tools:
    - `preguntar(mensaje: str, conversacion: str = "mcp") -> str` — `Agent.ask`; when an action is pending returns `Acción pendiente: <description>. Llama a confirmar con aprobar=true o false.`
    - `confirmar(aprobar: bool, conversacion: str = "mcp") -> str` — `Agent.confirm`.
    - Only if enabled in the config: `buscar_documentos(consulta: str) -> str` and `calcular_plazo(actuacion: str, fecha_notificacion: str, notificacion_electronica: bool = False) -> str`, both via `Agent.run_tool`, with the same descriptions as the built-in tools.
    - Never: `registrar_en_hoja`, `enviar_correo`.
    - `ValueError`/`AgentError` → returned as a Spanish text result (no traceback to the client).
  - CLI `agentes mcp CONFIG [--data .agentes]`: stdio server; all human-facing notices go to stderr (stdout is the protocol).
  - Import path of FastMCP in mcp 2.x: check after install (`mcp.server.fastmcp.FastMCP` in 1.x); write it once in `server.py`.

- [ ] **Step 1: Dependency:** `python -m uv add "mcp>=2.0"`; confirm the FastMCP import and the in-process call API (`list_tools`, `call_tool`) of the installed version.
- [ ] **Step 2: Failing tests** (async calls wrapped in `asyncio.run` or `anyio.run`; no pytest plugin):
  - `test_run_tool_audits_read_only` (law-firm config: `run_tool("calcular_plazo", {"actuacion": "reposicion", "fecha_notificacion": "02/03/2026"})` contains `Vence el 05/03/2026`; audit has 1 entry, thread `mcp`, status `executed`).
  - `test_run_tool_refuses_side_effects` (`enviar_correo` → ValueError with `efectos`; outbox empty; no audit row).
  - `test_mcp_lists_only_safe_tools` (tienda config → `{"preguntar", "confirmar", "buscar_documentos"}`; despacho-juridico adds `calcular_plazo`; never `enviar_correo`/`registrar_en_hoja`).
  - `test_mcp_preguntar_and_confirmar_flow` (scripted email tool call → `preguntar` text starts with `Acción pendiente: Enviar correo a`; `confirmar(aprobar=True)` → final reply; outbox has 1 email; audit `executed`).
  - `test_mcp_errors_are_text` (`confirmar` with nothing pending → `No hay ninguna acción pendiente de confirmar.`).
  - `test_mcp_command_writes_nothing_to_stdout_before_protocol` (CliRunner with the server's `run` monkeypatched → captured stdout empty, demo notice on stderr).
- [ ] **Step 3: Run → FAIL. Step 4: Implement. Step 5: Full checks → green.**
- [ ] **Step 6: Commit** `feat(mcp): expose the agent as an MCP server`.

### Task 5: Docs and phase close

**Files:**
- Modify: `README.md`, `README.es.md` (sections "HTTP API", "Web demo", "MCP server": commands, `AGENTES_API_KEY`, routes table, curl example with confirm, a Claude Desktop / MCP client config snippet using `uv run agentes mcp configs/despacho-juridico.yaml`), `.env.example` if it exists (add `AGENTES_API_KEY=`), the spec's Phase 4 line (note 4a done, MCP client deferred).

- [ ] **Step 1:** Write the sections; every command in them is run once and works as written (demo mode).
- [ ] **Step 2:** Full checks green; `git status` clean after commit.
- [ ] **Step 3: Commit** `docs: document HTTP API, web demo and MCP server`.
- [ ] **Step 4:** Spanish summary to the owner; merge only with her OK.

# Phase 2 — Tools & Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The agent can search the company's own documents (with citations), append rows to a sheet and send emails — side-effecting tools only after the user confirms — and every tool call is recorded in an audit log; all of it works offline in demo mode.

**Architecture:** `rag` loads `knowledge_dir` (md/txt/pdf) into chunks and searches them with BM25 offline, or with embeddings when a Gemini key exists. `tools` holds a registry of `ToolSpec`s built per config. The graph gains a `tools` node: `model → (tool calls?) → confirm gate (LangGraph interrupt for confirm_tools) → tools → model`. `audit` is an append-only SQLite table written by the tools node. `Agent.ask` now returns an `AgentReply` that may carry a pending confirmation, resolved with `Agent.confirm`.

**Tech Stack:** Phase 1 stack + rank-bm25, pypdf, langchain-text-splitters, langchain-google-genai embeddings, gspread + google-auth (optional backend), stdlib smtplib/email.

**Spec:** `docs/superpowers/specs/2026-10-30-agentes-ia-empresas-design.md`

## Global Constraints

- All Phase 1 constraints still apply (uv via `python -m uv`, ruff + `mypy --strict` + pytest green before every commit, English code / Spanish user text, UTF-8 I/O, author `Ricardo Porras <ricardoprs76@gmail.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- Tests never touch the network, Google APIs or a real SMTP server.
- Demo data is fictional. Default backends need no credentials: sheet → local CSV, email → outbox folder of `.eml` files.
- Credentials only via env vars: `GOOGLE_SERVICE_ACCOUNT_FILE`, `AGENTES_SHEET_ID`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Add them (empty) to `.env.example`.
- Tool names (Spanish, stable, used in YAML): `buscar_documentos`, `registrar_en_hoja`, `enviar_correo`.
- A tool not listed in the config's `tools` is never bound to the model and never executed even if the model asks for it.
- Every executed, rejected or failed tool call writes exactly one audit row.

## Review Focus

1. `knowledge_dir` missing, empty, or holding only unreadable files (scanned PDF without text, binary junk) → `buscar_documentos` answers "No encontré información sobre eso en los documentos de la empresa." instead of crashing; unreadable files are skipped with a warning (Task 2 test).
2. User rejects a confirmation → tool not executed, audit row `rejected`, agent tells the user it was cancelled (Task 6 test).
3. Process restarts while a confirmation is pending → the same thread still shows the pending action and can be confirmed (Task 6 test).
4. Side-effect backend fails (SMTP down, CSV locked) → audit row `error`, the agent gets a Spanish error text as tool result and the chat keeps running (Task 4 + Task 6 tests).
5. Model requests a tool that is not enabled, or passes invalid arguments → no execution, a Spanish error tool message, audit row `error` (Task 6 test).

---

### Task 1: Scripted test model with tool calls + demo model tool calls

**Files:**
- Modify: `tests/conftest.py`, `src/agentes/llm/demo.py`
- Test: `tests/llm/test_demo.py`

**Interfaces:**
- Produces:
  - `RecordingChatModel.replies: list[str | AIMessage]` — a str becomes `AIMessage(content=str)`, an `AIMessage` (possibly with `tool_calls`) is returned as-is; `bind_tools(...)` returns `self`.
  - `DemoChatModel.tool_names: frozenset[str] = frozenset()`; `bind_tools(tools)` returns a copy with `tool_names` set to the bound tools' names.
  - Demo rules, evaluated on the last message: if it is a `ToolMessage` → reply `"[modo demo] Resultado: " + tool_message.content`. Else on the last human text (lower-cased, word-boundary match): `buscar_documentos` bound and text contains `horario|precio|política|politica|garantía|garantia|documento` → tool call `buscar_documentos(consulta=<text>)`; `registrar_en_hoja` bound and text contains `registra|anota` → `registrar_en_hoja(datos={"nota": <text>})`; `enviar_correo` bound and text contains `correo|email` → `enviar_correo(para="cliente@ejemplo.com", asunto="Mensaje de prueba", cuerpo=<text>)`; else Phase 1 behaviour (greeting by **whole word**, fixing the deferred "chola" minor).
  - Tool call ids are deterministic: `f"demo-{n}"` with n = number of messages.

- [ ] **Step 1: Write failing tests:** `test_demo_calls_search_tool_when_bound`, `test_demo_does_not_call_unbound_tool`, `test_demo_calls_email_tool`, `test_demo_summarizes_tool_result`, `test_demo_greeting_whole_word_only` (`"la chola"` → generic answer), `test_bind_tools_returns_copy_with_names` (replaces `test_demo_bind_tools_returns_self`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Full suite + checks → PASS.
- [ ] **Step 5: Commit** `feat(llm): let the demo model call tools`.

### Task 2: Knowledge base (RAG) with citations

**Files:**
- Create: `src/agentes/rag/__init__.py`, `src/agentes/rag/loader.py`, `src/agentes/rag/search.py`
- Test: `tests/rag/test_loader.py`, `tests/rag/test_search.py`, fixtures under `tests/rag/docs/` (2 small `.md`, 1 `.txt`, 1 one-page `.pdf` generated in a fixture with pypdf/reportlab-free bytes — builder may commit a tiny PDF instead), plus a `.bin` junk file.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Chunk`: `text: str`, `source: str` (path relative to knowledge_dir, forward slashes), `page: int | None`.
  - `load_chunks(folder: Path, chunk_size: int = 800, overlap: int = 120) -> tuple[list[Chunk], list[str]]` — returns chunks and Spanish warnings (`"Se omitió <file>: <reason>"`); supports `.md`, `.txt`, `.pdf` (per page); other extensions ignored silently; missing folder → `([], ["La carpeta de documentos no existe: <path>"])`. Uses `RecursiveCharacterTextSplitter`.
  - `@dataclass(frozen=True) class Hit`: `chunk: Chunk`, `score: float`.
  - `class KnowledgeBase(Protocol)`: `search(self, query: str, k: int = 4) -> list[Hit]`.
  - `class Bm25KnowledgeBase`: `__init__(self, chunks: list[Chunk])`; tokenizer lower-cases, strips accents (NFKD) and splits on non-word; returns only hits with score > 0.
  - `class VectorKnowledgeBase`: `__init__(self, chunks: list[Chunk], embeddings: Embeddings)`; uses `InMemoryVectorStore`.
  - `build_knowledge_base(chunks: list[Chunk], env: Mapping[str, str] | None = None) -> KnowledgeBase` — Gemini key present → `VectorKnowledgeBase` with `GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")`; else BM25.
  - `format_hits(hits: list[Hit]) -> str` — Spanish text: each hit as `[n] <text>\n(Fuente: <source>[, página <p>])`; empty → `"No encontré información sobre eso en los documentos de la empresa."`

- [ ] **Step 1: Write failing tests:** `test_loads_md_txt_pdf_with_sources`, `test_pdf_pages_numbered`, `test_junk_and_textless_pdf_skipped_with_warning`, `test_missing_folder_returns_warning`, `test_bm25_finds_relevant_chunk` (query `"horario de atención"` hits `horarios.md`), `test_bm25_accent_insensitive` (`"garantia"` finds `"garantía"`), `test_bm25_no_match_returns_empty`, `test_vector_kb_uses_embeddings` (with `DeterministicFakeEmbedding`; assert returns k hits), `test_build_kb_without_key_is_bm25`, `test_format_hits_cites_source_and_page`, `test_format_no_hits_message`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Full suite + checks → PASS.
- [ ] **Step 5: Commit** `feat(rag): add document knowledge base with BM25 and embeddings`.

### Task 3: Audit log

**Files:**
- Create: `src/agentes/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Produces:
  - `AuditStatus = Literal["executed", "rejected", "error"]`.
  - `@dataclass(frozen=True) class AuditEntry`: `id: int`, `timestamp: datetime` (UTC, aware), `thread_id: str`, `tool: str`, `args: dict[str, Any]`, `status: AuditStatus`, `result: str`.
  - `class AuditLog`: `__init__(self, conn: sqlite3.Connection)` creates table `audit_log` if missing; `record(self, thread_id: str, tool: str, args: Mapping[str, Any], status: AuditStatus, result: str) -> AuditEntry`; `entries(self, thread_id: str | None = None, limit: int = 100) -> list[AuditEntry]` newest first. Args stored as JSON with `ensure_ascii=False`. No update/delete methods (append-only).

- [ ] **Step 1: Write failing tests:** `test_record_and_read_back`, `test_entries_newest_first_and_limit`, `test_filter_by_thread`, `test_accented_args_round_trip`, `test_survives_reopen`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(audit): add append-only audit log`.

### Task 4: Sheet and email backends

**Files:**
- Create: `src/agentes/integrations/__init__.py`, `src/agentes/integrations/sheets.py`, `src/agentes/integrations/email.py`
- Test: `tests/integrations/test_sheets.py`, `tests/integrations/test_email.py`

**Interfaces:**
- Produces:
  - `class SheetBackend(Protocol)`: `append_row(self, values: Mapping[str, str]) -> str` (returns Spanish confirmation text).
  - `class CsvSheet(SheetBackend)`: `__init__(self, path: Path)`; adds a `fecha` column (ISO UTC) first; writes header on first write; new keys extend the header (rewrite file); UTF-8 with BOM (`utf-8-sig`) so Excel opens accents correctly. Returns `"Fila registrada en <file name>."`
  - `class GoogleSheet(SheetBackend)`: `__init__(self, sheet_id: str, service_account_file: Path)`; lazy gspread import; appends to first worksheet. (Unit test only with a fake gspread client injected via `client` kwarg.)
  - `sheet_from_env(data_dir: Path, env: Mapping[str, str] | None = None) -> SheetBackend` — both `GOOGLE_SERVICE_ACCOUNT_FILE` and `AGENTES_SHEET_ID` set → `GoogleSheet`; else `CsvSheet(data_dir / "hoja.csv")`.
  - `class Mailer(Protocol)`: `send(self, to: str, subject: str, body: str) -> str`.
  - `class OutboxMailer`: `__init__(self, folder: Path)`; writes an RFC 5322 `.eml` (`email.message.EmailMessage`, UTF-8) named `<UTC timestamp>-<slug>.eml`; returns `"Correo guardado en la bandeja de salida: <file name>"`.
  - `class SmtpMailer`: `__init__(self, host: str, port: int, user: str, password: str, sender: str, smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP)`; STARTTLS; returns `"Correo enviado a <to>."`.
  - `mailer_from_env(data_dir: Path, env: Mapping[str, str] | None = None) -> Mailer` — `SMTP_HOST` set → `SmtpMailer` (port default 587); else `OutboxMailer(data_dir / "bandeja_salida")`.
  - Recipient validation in both mailers: must match `^[^@\s]+@[^@\s]+\.[^@\s]+$`, else `ValueError("Dirección de correo no válida: <to>")`.

- [ ] **Step 1: Write failing tests:** `test_csv_writes_header_and_rows`, `test_csv_new_column_extends_header`, `test_csv_accents_excel_bom`, `test_sheet_from_env_defaults_to_csv`, `test_google_sheet_appends_with_fake_client`, `test_outbox_writes_eml` (parse back with `email.message_from_bytes`, subject/body with accents), `test_invalid_recipient_rejected`, `test_smtp_uses_starttls_and_login` (fake SMTP class records calls), `test_mailer_from_env_defaults_to_outbox`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(integrations): add CSV/Google Sheets and outbox/SMTP backends`.

### Task 5: Tool registry

**Files:**
- Create: `src/agentes/tools/__init__.py`, `src/agentes/tools/registry.py`, `src/agentes/tools/builtin.py`
- Modify: `src/agentes/config/schema.py` (validate tool names against registry names)
- Test: `tests/tools/test_registry.py`, extend `tests/config/test_loader.py`

**Interfaces:**
- Consumes: `KnowledgeBase`, `format_hits`, `load_chunks`, `build_knowledge_base` (Task 2); `SheetBackend`, `Mailer`, `sheet_from_env`, `mailer_from_env` (Task 4).
- Produces:
  - `TOOL_NAMES: frozenset[str] = frozenset({"buscar_documentos", "registrar_en_hoja", "enviar_correo"})`; `AgentConfig` rejects unknown names in `tools` with `ConfigError` message containing `Herramienta desconocida: <name>`.
  - `SIDE_EFFECT_TOOLS = frozenset({"registrar_en_hoja", "enviar_correo"})`.
  - `@dataclass(frozen=True) class ToolContext`: `knowledge: KnowledgeBase`, `sheet: SheetBackend`, `mailer: Mailer`, `warnings: tuple[str, ...]`.
  - `build_context(config: AgentConfig, data_dir: Path, env: Mapping[str, str] | None = None) -> ToolContext` — loads `knowledge_dir` only if `buscar_documentos` is enabled.
  - `build_tools(config: AgentConfig, ctx: ToolContext) -> list[BaseTool]` — only enabled tools, in config order; LangChain `StructuredTool`s with Spanish descriptions; args: `buscar_documentos(consulta: str)`, `registrar_en_hoja(datos: dict[str, str])`, `enviar_correo(para: str, asunto: str, cuerpo: str)`.

- [ ] **Step 1: Write failing tests:** `test_only_enabled_tools_built`, `test_search_tool_returns_cited_text`, `test_sheet_tool_appends_row`, `test_email_tool_writes_outbox`, `test_unknown_tool_name_rejected_in_config`, `test_context_skips_knowledge_when_search_disabled`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(tools): add tool registry with search, sheet and email tools`.

### Task 6: Graph with tools, confirmation and audit

**Files:**
- Modify: `src/agentes/graph/builder.py`, `src/agentes/graph/__init__.py`, `src/agentes/agent.py`
- Test: `tests/graph/test_tools_flow.py`; update `tests/graph/test_agent.py`, `tests/test_cli.py` for the new return type

**Interfaces:**
- Consumes: `build_tools`, `ToolContext`, `SIDE_EFFECT_TOOLS` (Task 5); `AuditLog` (Task 3).
- Produces:
  - `build_graph(config, model, checkpointer, tools: Sequence[BaseTool] = (), audit: AuditLog | None = None)` — nodes `"model"`, `"tools"`; `model` binds tools when any; conditional edge `model → tools` if the last AIMessage has tool calls else `END`; `tools → model`. Inside `tools`, for each call: unknown/not-enabled name or invalid args → `ToolMessage` with Spanish error + audit `error`; name in `config.confirm_tools` → `interrupt({"tool": name, "args": args, "tool_call_id": id})` and resume value `bool`: `False` → `ToolMessage("El usuario canceló la acción.")` + audit `rejected`; tool exception → `ToolMessage("Error al ejecutar <name>: <exc>")` + audit `error`; success → result + audit `executed`. Read-only tools audited too.
  - `@dataclass(frozen=True) class PendingAction`: `tool: str`, `args: dict[str, Any]`, `description: str` (Spanish, e.g. `Enviar correo a x@y.com con asunto "…"` / `Registrar en la hoja: clave=valor, …`).
  - `@dataclass(frozen=True) class AgentReply`: `text: str`, `pending: PendingAction | None = None`.
  - `Agent.__init__(self, config, selection, db_path, data_dir: Path | None = None, env: Mapping[str, str] | None = None)` — `data_dir` default `db_path.parent`; builds ToolContext, tools, AuditLog (same SQLite connection); exposes `warnings: tuple[str, ...]` and `audit: AuditLog`.
  - `Agent.ask(thread_id, text) -> AgentReply`; `Agent.confirm(thread_id, approved: bool) -> AgentReply` (raises `ValueError("No hay ninguna acción pendiente de confirmar.")` if none); `Agent.pending(thread_id) -> PendingAction | None` (reads the interrupt from the checkpoint — works after restart). `ask` while an action is pending raises `ValueError("Primero confirma o cancela la acción pendiente.")`. Orphan-message cleanup from Phase 1 kept.

- [ ] **Step 1: Write failing tests** (scripted `RecordingChatModel` emitting tool calls): `test_read_only_tool_runs_without_confirmation_and_is_audited`, `test_side_effect_tool_waits_for_confirmation`, `test_confirm_executes_and_audits`, `test_reject_cancels_and_audits`, `test_pending_survives_restart`, `test_ask_while_pending_rejected`, `test_confirm_without_pending_raises`, `test_disabled_tool_call_not_executed`, `test_invalid_args_reported_as_error`, `test_backend_failure_audited_as_error_and_reply_continues`, `test_demo_mode_end_to_end_search` (DemoChatModel + fixture docs → reply contains `Fuente:`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite + checks → PASS (Phase 1 tests updated to `.text`).
- [ ] **Step 5: Commit** `feat(graph): add tool execution with human confirmation and audit`.

### Task 7: CLI for tools and audit + demo docs

**Files:**
- Modify: `src/agentes/cli.py`, `configs/ejemplo.yaml`, `.env.example`
- Create: `data/demo/ferreteria/horarios.md`, `data/demo/ferreteria/garantias.md`, `data/demo/ferreteria/domicilios.md` (fictional)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Agent`, `AgentReply`, `PendingAction` (Task 6); `AuditLog.entries` (Task 3).
- Produces:
  - `chat` prints each `Agent.warnings` line once at start (prefixed `Aviso: `); on a pending action prints `Acción pendiente: <description>` and prompts `¿Confirmas? (s/n): ` — `s`/`si`/`sí` approve, `n`/`no` reject, anything else re-asks; at start, if the thread already has a pending action, it asks for it first.
  - New `--data PATH` option (default `.agentes/`) used as `data_dir`; `--db` default becomes `<data>/memoria.sqlite`.
  - `agentes auditoria CONFIG [--thread TEXT] [--limit INT=20] [--data PATH]` prints one line per entry: `<local time> | <thread> | <tool> | <status in Spanish: ejecutada/cancelada/error> | <args JSON>`; empty → `No hay acciones registradas.`
  - `configs/ejemplo.yaml`: `knowledge_dir: ../data/demo/ferreteria`, `tools: [buscar_documentos, registrar_en_hoja, enviar_correo]`, `confirm_tools: [registrar_en_hoja, enviar_correo]`.

- [ ] **Step 1: Write failing tests:** `test_chat_search_shows_source` (demo, `"¿Cuál es el horario?"` → output contains `Fuente: horarios.md`), `test_chat_email_confirm_yes_writes_outbox`, `test_chat_email_confirm_no_cancels`, `test_chat_confirmation_reasks_on_invalid_answer`, `test_chat_resumes_pending_on_restart`, `test_auditoria_lists_entries`, `test_auditoria_empty`, `test_chat_prints_knowledge_warnings`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite + checks → PASS; manual smoke in demo mode (search, email with confirm, `auditoria`).
- [ ] **Step 5: Commit** `feat(cli): confirm side-effect actions and show the audit log`.

### Task 8: Phase 2 docs

**Files:**
- Modify: `README.md`, `README.es.md`, `docs/architecture.md`

- [ ] **Step 1:** Add "Tools & safety" section (EN/ES): the three tools, default offline backends vs. env-configured real ones (table of env vars), confirmation flow example transcript, `agentes auditoria`; update config table (`tools`, `confirm_tools`, `knowledge_dir` no longer "Phase 2"); tick Phase 2 in roadmap. Architecture: update Mermaid with `tools` node, interrupt gate, audit table; add decision "BM25 offline fallback so RAG works without keys".
- [ ] **Step 2:** All checks green.
- [ ] **Step 3: Commit** `docs: document tools, confirmation and audit log`.
- [ ] **Step 4:** Summarize Phase 2 to the owner in Spanish and wait for approval before Phase 3.

# Phase 1 — Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested, CI-checked Python package where a business is described in one YAML file and a LangGraph agent chats in Spanish from the command line, with per-conversation memory, using Gemini/Claude/OpenAI or a keyless demo model.

**Architecture:** `config` (Pydantic + YAML) → `llm.factory` picks a chat model (real provider or `DemoChatModel`) → `graph.builder` compiles a LangGraph `StateGraph` with a SQLite checkpointer → `Agent` facade (`ask(thread_id, text)`) → Typer CLI. Tools, RAG, API come in later phases; Phase 1 graph is a single model node designed so a tool node can be added in Phase 2.

**Tech Stack:** Python 3.12, uv, LangGraph, langchain-core, langchain-google-genai / langchain-anthropic / langchain-openai, langgraph-checkpoint-sqlite, Pydantic v2, PyYAML, Typer, pytest, ruff, mypy, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-30-agentes-ia-empresas-design.md`

## Global Constraints

- Python `>=3.12`; managed with `uv` (`uv sync`, `uv run`). Package name `agentes`, src layout `src/agentes/`.
- `ruff check`, `ruff format --check`, `mypy --strict src` and `pytest` must all pass before every commit.
- Identifiers, docstrings, code comments in English; everything the agent/CLI says to an end user in Spanish.
- Tests never call real LLM APIs. Live tests only behind `AGENTES_LIVE_TESTS=1` (none required in Phase 1).
- No secrets in the repo. Keys only via env vars `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`; `.env` git-ignored, `.env.example` committed.
- Commit author: `Ricardo Porras <ricardoprs76@gmail.com>`; every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Conventional-commit prefixes (`feat:`, `test:`, `chore:`, `docs:`, `ci:`).
- License MIT.
- All file I/O uses `encoding="utf-8"` (Windows dev machine; Spanish text).

## Review Focus

1. Config file missing, invalid YAML, or a wrong field → one clear Spanish error line naming the file/field, exit code 2, no traceback (Task 2, Task 5 tests).
2. API key env var set but empty/whitespace → treated as absent → demo mode with a visible "modo demo" notice, not a provider crash (Task 3 test).
3. Conversation memory survives a process restart when the same SQLite file and thread id are reused (Task 4 test).
4. Empty or whitespace-only user message → not sent to the model; CLI just re-prompts (Task 4 + Task 5 tests).
5. Accented Spanish text (ñ, á, ¿) round-trips through YAML, model, and CLI output on Windows without mojibake (Task 2 + Task 5 tests).

---

### Task 1: Project scaffold and CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `LICENSE`, `README.md` (stub), `src/agentes/__init__.py`, `src/agentes/py.typed`, `tests/test_package.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: importable package `agentes` with `agentes.__version__: str == "0.1.0"`; console script `agentes = "agentes.cli:app"` declared (module created in Task 5).

- [ ] **Step 1:** `pip install uv` (user-level) and confirm `uv --version`.
- [ ] **Step 2: Write the failing test** `tests/test_package.py::test_version` → `assert agentes.__version__ == "0.1.0"`.
- [ ] **Step 3:** Create `pyproject.toml` (hatchling build, deps above, dev group: pytest, pytest-cov, ruff, mypy, types-PyYAML), ruff config (line-length 100, rules `E,F,I,B,UP,SIM,RUF`), mypy `strict = true`, pytest `testpaths=["tests"]`. `.gitignore` covers `.venv/ .env *.sqlite __pycache__/ .mypy_cache/ .ruff_cache/ dist/`. `.env.example` lists the three key vars empty.
- [ ] **Step 4:** `uv sync` then `uv run pytest` → PASS; `uv run ruff check . && uv run ruff format --check . && uv run mypy src` → clean.
- [ ] **Step 5:** CI workflow: on push/PR, ubuntu-latest + windows-latest, `astral-sh/setup-uv`, `uv sync --frozen`, the four checks. Commit `uv.lock` too.
- [ ] **Step 6: Commit** `chore: scaffold project with uv, ruff, mypy, pytest and CI`.

### Task 2: Company config schema

**Files:**
- Create: `src/agentes/config/__init__.py`, `src/agentes/config/schema.py`, `src/agentes/config/loader.py`, `configs/ejemplo.yaml`
- Test: `tests/config/test_loader.py`

**Interfaces:**
- Produces:
  - `class ModelConfig(BaseModel)`: `provider: Literal["gemini","anthropic","openai"] = "gemini"`, `model: str | None = None` (provider default if None), `temperature: float = Field(0.2, ge=0, le=1)`.
  - `class AgentConfig(BaseModel)` (`extra="forbid"`): `id: str` (slug regex `^[a-z0-9-]+$`), `company_name: str`, `sector: str`, `language: str = "es"`, `tone: str`, `rules: list[str] = []`, `model: ModelConfig = ModelConfig()`, `tools: list[str] = []`, `confirm_tools: list[str] = []`, `knowledge_dir: Path | None = None`.
  - `AgentConfig.system_prompt() -> str` — Spanish prompt containing company name, sector, tone, each rule as a bullet, and the fixed line `Si no sabes la respuesta, dilo claramente; nunca inventes datos.`
  - `class ConfigError(Exception)` with Spanish message.
  - `load_config(path: Path) -> AgentConfig` — reads UTF-8 YAML; raises `ConfigError` for missing file (`No se encontró el archivo de configuración: <path>`), invalid YAML (`YAML inválido en <path>: <detail>`), validation errors (`Campo inválido '<loc>' en <path>: <msg>`, first error); resolves relative `knowledge_dir` against the YAML's folder; `confirm_tools` must be a subset of `tools` (else `ConfigError`).

- [ ] **Step 1: Write failing tests:** `test_loads_example_config` (configs/ejemplo.yaml loads, `company_name == "Ferretería El Tornillo"`), `test_missing_file_raises_config_error`, `test_invalid_yaml_raises_config_error`, `test_unknown_field_rejected`, `test_confirm_tools_must_be_subset`, `test_relative_knowledge_dir_resolved`, `test_system_prompt_contains_rules_and_no_invent_line`, `test_accents_round_trip` (tone `"cálido y cercano, ¿en qué te ayudo?"` appears unchanged in `system_prompt()`).
- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3:** Implement schema + loader + `configs/ejemplo.yaml` (fictional hardware shop, 3 rules, no tools).
- [ ] **Step 4:** Run tests + checks → PASS.
- [ ] **Step 5: Commit** `feat(config): add YAML company config schema and loader`.

### Task 3: LLM provider factory with keyless demo model

**Files:**
- Create: `src/agentes/llm/__init__.py`, `src/agentes/llm/factory.py`, `src/agentes/llm/demo.py`
- Test: `tests/llm/test_factory.py`, `tests/llm/test_demo.py`

**Interfaces:**
- Consumes: `ModelConfig` (Task 2).
- Produces:
  - `DEFAULT_MODELS: dict[str, str]` = `{"gemini": "gemini-2.5-flash", "anthropic": "claude-haiku-5-5", "openai": "gpt-4.1-mini"}`; `API_KEY_ENV` = `{"gemini": "GOOGLE_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}`.
  - `class DemoChatModel(BaseChatModel)`: deterministic; reply = `"[modo demo] "` + a canned Spanish answer chosen by keyword in the last human message (saludo → greeting using company name taken from the system message; otherwise a generic "En modo demo no puedo consultar información real…" answer). `_llm_type = "demo"`. Must support `bind_tools` returning self (so Phase 2 graph works in demo mode).
  - `@dataclass(frozen=True) class ModelSelection`: `model: BaseChatModel`, `is_demo: bool`, `provider: str`, `model_name: str`.
  - `build_chat_model(cfg: ModelConfig, env: Mapping[str, str] | None = None) -> ModelSelection` — `env` defaults to `os.environ`; key missing or blank → `DemoChatModel`, `is_demo=True`; otherwise lazily import the provider's LangChain class and construct with key + temperature.

- [ ] **Step 1: Write failing tests:** `test_no_key_returns_demo`, `test_blank_key_returns_demo` (`"   "`), `test_gemini_key_builds_gemini_model` (assert class name `ChatGoogleGenerativeAI`, `model_name == "gemini-2.5-flash"`, no network call at construction), same for anthropic/openai, `test_explicit_model_name_overrides_default`, `test_demo_greeting_mentions_company`, `test_demo_reply_is_deterministic`, `test_demo_bind_tools_returns_self`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run tests + checks → PASS.
- [ ] **Step 5: Commit** `feat(llm): add provider factory with keyless demo model`.

### Task 4: LangGraph agent with persistent memory

**Files:**
- Create: `src/agentes/graph/__init__.py`, `src/agentes/graph/state.py`, `src/agentes/graph/builder.py`, `src/agentes/agent.py`
- Test: `tests/graph/test_agent.py`, `tests/conftest.py` (fixtures: example config, `FakeMessagesListChatModel`-based scripted model that also records the messages it received)

**Interfaces:**
- Consumes: `AgentConfig.system_prompt()` (Task 2), `ModelSelection` (Task 3).
- Produces:
  - `class AgentState(TypedDict)`: `messages: Annotated[list[AnyMessage], add_messages]`.
  - `build_graph(config: AgentConfig, model: BaseChatModel, checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph` — nodes: `"model"` (prepends `SystemMessage(config.system_prompt())` at call time, never stored in state); edges `START → model → END`. Node names are stable so Phase 2 can add `"tools"`.
  - `class Agent`: `__init__(self, config: AgentConfig, selection: ModelSelection, db_path: Path)`; `ask(self, thread_id: str, text: str) -> str` (strips text; empty → raises `ValueError("El mensaje está vacío.")` without calling the model); `history(self, thread_id: str) -> list[AnyMessage]`; `is_demo: bool` property; context manager closing the SQLite connection. Uses `SqliteSaver` from `langgraph-checkpoint-sqlite`.

- [ ] **Step 1: Write failing tests:** `test_ask_returns_model_reply`, `test_system_prompt_sent_but_not_stored`, `test_memory_within_thread` (second call's model input contains first exchange), `test_threads_isolated`, `test_memory_survives_restart` (new `Agent` on same `db_path` sees prior history), `test_empty_message_rejected_without_model_call`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run tests + checks → PASS.
- [ ] **Step 5: Commit** `feat(graph): add LangGraph agent with SQLite conversation memory`.

### Task 5: Command-line interface

**Files:**
- Create: `src/agentes/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `ConfigError` (Task 2), `build_chat_model` (Task 3), `Agent` (Task 4).
- Produces: Typer `app` with:
  - `agentes validate CONFIG` → prints `Configuración válida: <company_name> (<sector>)`, exit 0; `ConfigError` → message to stderr, exit 2.
  - `agentes chat CONFIG [--thread TEXT=default] [--db PATH=.agentes/memoria.sqlite]` → if demo prints once `Modo demo: no hay clave de IA configurada. Las respuestas son de ejemplo.`; loop reading stdin with prompt `Tú: `, prints `<company_name>: <reply>`; blank lines re-prompt; `salir` or EOF ends with `¡Hasta pronto!`. Creates the db folder if missing. Forces UTF-8 stdout (`sys.stdout.reconfigure(encoding="utf-8")` when available).

- [ ] **Step 1: Write failing tests** (Typer `CliRunner`, demo mode via empty env): `test_validate_ok`, `test_validate_missing_file_exit_2_no_traceback`, `test_chat_demo_notice_and_reply`, `test_chat_blank_line_reprompts`, `test_chat_exit_word`, `test_chat_accented_output` (input `¿Hola, señor?` and output contains `[modo demo]` with no `�`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run tests + checks → PASS; manual smoke: `uv run agentes chat configs/ejemplo.yaml` answers in demo mode.
- [ ] **Step 5: Commit** `feat(cli): add validate and chat commands`.

### Task 6: Phase 1 docs

**Files:**
- Modify: `README.md`; Create: `README.es.md`, `docs/architecture.md`

- [ ] **Step 1:** README (EN): one-paragraph pitch, CI badge, quickstart (`uv sync`, `uv run agentes chat configs/ejemplo.yaml`, optional `GOOGLE_API_KEY`), config file reference table, roadmap of the 5 phases with Phase 1 checked. README.es.md: same in Spanish. `docs/architecture.md`: Mermaid diagram config → factory → graph → Agent → CLI. No "made with AI" emphasis.
- [ ] **Step 2:** All checks green.
- [ ] **Step 3: Commit** `docs: add Phase 1 README (EN/ES) and architecture overview`.
- [ ] **Step 4:** Summarize Phase 1 to the owner in Spanish and wait for approval before Phase 2.

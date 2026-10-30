# Agentes IA para Empresas — Design

Date: 2026-10-30
Owner: María (GitHub portfolio project)

## Intent and why

A new public GitHub project, "Agentes IA para Empresas": a configurable AI-agent
platform that a business can adapt to its sector by editing one config file.

The owner's goal: anyone (recruiters, tech leads, potential clients) who opens the
repo should conclude **"this person is an excellent programmer."** So code quality,
architecture, tests, CI and documentation matter as much as the demo working.
Secondary goal: reuse it as the base for paid agent projects for small businesses
in Colombia/Latam (she is a lawyer moving into tech; legal sector is her edge).

## Goals

- Generic core, concrete outside: one engine + 3 ready sector configs
  (law firm = flagship, shop, clinic).
- Stack matches what AI-engineer job postings ask for most (web research
  2026-10-30): **Python** primary, **LangGraph**, **FastAPI**, **RAG**, **MCP**,
  plus **TypeScript** via a custom n8n node.
- Works for free out of the box (Gemini free tier) and with Claude / OpenAI via
  config — provider-agnostic.
- Anyone can try it in ~5 minutes: `docker compose up`.
- Visible safety: confirmation before side-effecting actions (human-in-the-loop),
  audit log of every tool call, answers grounded in the company's documents with
  "I don't know" instead of inventing.
- Built in phases, each phase leaves the repo in a working, tested, presentable state.

## Non-goals

- Not a SaaS: no multi-tenant billing, user accounts, or hosted production service.
- No real customer data, ever. Demo data is fictional.
- No WhatsApp Business API integration in code (needs Meta approval); WhatsApp is
  only shown as an n8n flow template the user wires up themselves.
- No custom frontend framework app; the demo UI stays simple.

## Anti-goals (failure even if it works)

- Looks like a tutorial copy or "yet another LangChain chatbot".
- Whole agent built as n8n drag-and-drop (reads as no-code, undermines the goal).
- Secrets / API keys committed; failing CI badge; untested code; messy commits.
- README that stresses "made with AI" (owner's profile rule: at most a mild
  mention). Commit trailers are fine — owner chose them.

## Constraints

- Windows 11 dev machine; must also run on Linux (Docker, GitHub Actions).
- Python 3.12, dependency management with `uv`; lint/format with `ruff`, types
  with `mypy` (strict on `src/`), tests with `pytest`.
- Code, identifiers, docstrings and main README in **English** (recruiter
  audience); a `README.es.md` in Spanish. (Builder's/assistant's call.)
- License MIT.
- Local project folder: `C:\Users\ricar\AgentesIAEmpresas`. Repo name:
  `agentes-ia-empresas`. Publishing to GitHub happens only in the last phase and
  only with the owner's explicit go-ahead (she gives the account/login).
- Tests must not call real LLM APIs: use a fake/scripted model; live tests are
  opt-in behind an env flag.

## Architecture (decided)

```
src/agentes/
  config/      Pydantic schema for sector config (YAML): name, tone, system rules,
               enabled tools, knowledge folder, model provider, which tools need
               confirmation
  llm/         provider factory (gemini | anthropic | openai) via LangChain chat models
  graph/       LangGraph agent: state, nodes (plan/answer, tool call, confirmation
               interrupt, finalize), checkpointer (SQLite) for conversations
  tools/       tool registry; each tool = typed function + metadata (side_effect: bool)
  rag/         ingest folder (md/pdf/txt) → chunks → embeddings → local vector store
               (Chroma or similar); retrieval tool with source citations
  audit/       append-only audit log (SQLite/JSONL) of every tool call and decision
  api/         FastAPI: POST /chat, POST /chat/{id}/confirm, GET /audit, GET /health,
               OpenAPI docs; API-key auth via header
  mcp/         MCP server exposing the agent's tools (and an MCP client so the agent
               can use external MCP tools)
configs/       despacho-juridico.yaml, tienda.yaml, clinica.yaml
data/demo/     fictional documents per sector
integrations/n8n/
  flows/       importable JSON workflows (email→agent→Sheets; webhook/WhatsApp→agent)
  node/        custom n8n node package in TypeScript ("Agentes IA para Empresas")
demo/          simple web chat UI served by FastAPI (static HTML/JS) — builder may
               choose Streamlit/Gradio instead if simpler, but keep it light
tests/         unit + integration (fake LLM), API tests
docker-compose.yml   agent + n8n
.github/workflows/   CI: ruff, mypy, pytest, n8n node build/lint
docs/          architecture diagram, ADRs for key choices
```

## Phases

1. **Core** — project scaffold (uv, ruff, mypy, pytest, CI), config schema,
   LLM provider factory, LangGraph agent with conversation memory, CLI to chat
   with a config. Tests with fake LLM.
2. **Tools & safety** — tool registry, RAG over company docs with citations,
   Google Sheets + email tools (email can default to a "draft/outbox file" mode so
   the demo needs no credentials), human-in-the-loop confirmation for
   side-effecting tools, audit log.
3. **Sector examples** — the 3 configs + fictional demo documents; law firm is
   the richest (contract clause review, deadline tracking, FAQ for clients).
4. **API & demo** — FastAPI service, auth, web chat demo, MCP server.
   4b. **n8n integration** — flow templates, custom TypeScript node, docker-compose
   with n8n + agent.
5. **Presentation** — README (EN) + README.es.md with GIF, architecture diagram,
   badges, Dockerfile polish, final review; publish to GitHub with the owner.

Each phase ends with: all checks green, README section updated, a short summary
to the owner in Spanish.

## Decisions after builder check

Owner decided:
- **Commits keep the `Co-Authored-By: Claude` trailer** (her explicit choice). Author
  identity: her name + her email from the start, so history never needs rewriting.
- **Agent language and demo data in Spanish; law-firm example uses real Colombian
  rules**: business days, Colombian holidays (incl. Ley Emiliani moved holidays and
  Easter-based ones), procedural terms (CGP), judicial vacancy (Dec 20–Jan 10 and
  Semana Santa). Deadline calculator is its own tested module.
- **Owner approves at the end of every phase** before the next one starts.

Assistant's calls (owner can override):
- **Demo mode without any API key**: if no key is set, the agent runs on a scripted
  demo model + small local embeddings, clearly labelled "modo demo"; with a free
  Gemini key it uses the real model. `docker compose up` always works.
- **n8n node**: built, linted and installed locally into the docker-compose n8n;
  npm publishing is out of scope for now.
- **Email**: tool interface designed provider-agnostic; implementations = outbox
  file (default) + SMTP. Gmail OAuth deferred to a paid project.

## Left to the builder

- Exact vector store, embedding model (prefer free/local or Gemini embeddings),
  chunking parameters.
- Internal module names below the top-level layout; prompt wording.
- Demo UI technology within "keep it light".
- Which concrete Google Sheets library and auth flow (service account suggested).

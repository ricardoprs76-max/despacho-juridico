# Agentes IA para Empresas

> [Leer en español](README.es.md)

**One engine, many businesses.** Describe a company in a single YAML file — its name,
sector, tone and rules — and get a Spanish-speaking AI agent with persistent memory,
built on [LangGraph](https://github.com/langchain-ai/langgraph). Swap the file and the
same engine serves a law firm, a hardware store or a clinic.

- **Provider-agnostic:** Google Gemini (free tier), Anthropic Claude or OpenAI, chosen in config.
- **Runs with zero keys:** without an API key it starts in a clearly labelled *demo mode*,
  so anyone can try it in a minute.
- **Persistent conversations:** each conversation thread is checkpointed in SQLite and
  survives restarts.
- **Strict quality bar:** `mypy --strict`, `ruff`, and a test suite that never calls a
  real LLM, run in CI on Linux and Windows.

## Quickstart

```bash
pip install uv            # if you don't have it
uv sync
uv run agentes validate configs/ejemplo.yaml
uv run agentes chat configs/ejemplo.yaml
```

To use a real model, copy `.env.example` to `.env` (or export the variable) and set
`GOOGLE_API_KEY` — a free key from [Google AI Studio](https://aistudio.google.com/apikey)
is enough. `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` work the same way.

```
$ uv run agentes chat configs/ejemplo.yaml --thread cliente-42
Tú: hola
Ferretería El Tornillo: ¡Hola! Soy el asistente de Ferretería El Tornillo. ¿En qué te ayudo?
Tú: salir
¡Hasta pronto!
```

## Company config

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Slug (`a-z`, `0-9`, `-`). |
| `company_name` | yes | Shown in replies and in the system prompt. |
| `sector` | yes | Business sector, e.g. `despacho jurídico`. |
| `tone` | yes | How the agent should sound. |
| `rules` | no | List of rules the agent must follow. |
| `model.provider` | no | `gemini` (default), `anthropic` or `openai`. |
| `model.model` | no | Model name; a sensible default per provider. |
| `model.temperature` | no | `0`–`1`, default `0.2`. |
| `tools`, `confirm_tools` | no | Enabled tools and those needing human confirmation (Phase 2). |
| `knowledge_dir` | no | Folder with the company's documents, relative to the YAML (Phase 2). |

Unknown fields are rejected, and every config error is reported as one clear line.

## Development

```bash
uv run pytest          # tests (no network, no API keys)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # strict type checking
```

Architecture overview: [docs/architecture.md](docs/architecture.md).

## Roadmap

- [x] **Phase 1 — Core:** config schema, provider factory with demo mode, LangGraph agent with memory, CLI.
- [ ] **Phase 2 — Tools & safety:** RAG over company documents with citations, Sheets and email tools, human-in-the-loop confirmation, audit log.
- [ ] **Phase 3 — Sector examples:** law firm (Colombian legal deadlines), shop, clinic.
- [ ] **Phase 4 — API & integrations:** FastAPI service, web demo, MCP server, n8n flows and a custom n8n node.
- [ ] **Phase 5 — Presentation:** Docker, demo GIF, final polish.

## License

[MIT](LICENSE)

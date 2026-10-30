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
- **Grounded answers:** the agent searches the company's own documents (Markdown, text, PDF)
  and cites the source file and page.
- **Human in the loop:** actions with side effects (writing to a sheet, sending email) wait
  for an explicit yes/no, and every tool call lands in an append-only audit log.
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
Tú: ¿Hasta qué hora abren el sábado?
Ferretería El Tornillo: Los sábados atendemos de 8:00 a. m. a 2:00 p. m. (Fuente: horarios.md)
Tú: Envíale a ana@ejemplo.com la política de garantías
Acción pendiente: Enviar correo a ana@ejemplo.com con asunto "Política de garantías"
¿Confirmas? (s/n): s
Ferretería El Tornillo: Listo, el correo quedó enviado.
Tú: salir
¡Hasta pronto!

$ uv run agentes auditoria configs/ejemplo.yaml
2026-10-30 08:11 | cliente-42 | enviar_correo | ejecutada | {"para": "ana@ejemplo.com", ...}
2026-10-30 08:10 | cliente-42 | buscar_documentos | ejecutada | {"consulta": "horario sábado"}
```

## Tools & safety

| Tool | What it does | Default backend (no setup) | Real backend (env vars) |
|------|--------------|----------------------------|-------------------------|
| `buscar_documentos` | Searches `knowledge_dir` (`.md`, `.txt`, `.pdf`) and returns passages with their source | BM25 keyword search, offline | Gemini embeddings when `GOOGLE_API_KEY` is set |
| `registrar_en_hoja` | Appends a row | `<data>/hoja.csv` (opens in Excel) | Google Sheets: `GOOGLE_SERVICE_ACCOUNT_FILE`, `AGENTES_SHEET_ID` |
| `enviar_correo` | Sends an email | `.eml` files in `<data>/bandeja_salida/` | SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` |

- Only tools listed in `tools` are offered to the model; a call to any other tool is refused.
- Tools listed in `confirm_tools` pause the conversation (a LangGraph `interrupt`) until the
  user answers. The pending question is checkpointed, so it survives a restart.
- Invalid arguments and backend failures become a Spanish message for the model, never a crash.
- `agentes auditoria CONFIG [--thread ID] [--limit N]` lists every executed, cancelled or
  failed action. The log has no edit or delete operations.
- `--data PATH` (default `.agentes/`) holds memory, outbox and sheet.

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
| `tools` | no | Enabled tools: `buscar_documentos`, `registrar_en_hoja`, `enviar_correo`. |
| `confirm_tools` | no | Subset of `tools` that needs a human yes/no before running. |
| `knowledge_dir` | no | Folder with the company's documents, relative to the YAML. |

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
- [x] **Phase 2 — Tools & safety:** RAG over company documents with citations, Sheets and email tools, human-in-the-loop confirmation, audit log.
- [ ] **Phase 3 — Sector examples:** law firm (Colombian legal deadlines), shop, clinic.
- [ ] **Phase 4 — API & integrations:** FastAPI service, web demo, MCP server, n8n flows and a custom n8n node.
- [ ] **Phase 5 — Presentation:** Docker, demo GIF, final polish.

## License

[MIT](LICENSE)

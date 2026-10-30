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
uv run agentes validate configs/tienda.yaml
uv run agentes chat configs/tienda.yaml
uv run agentes chat configs/despacho-juridico.yaml
```

To use a real model, copy `.env.example` to `.env` (or export the variable) and set
`GOOGLE_API_KEY` — a free key from [Google AI Studio](https://aistudio.google.com/apikey)
is enough. `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` work the same way.

```
$ uv run agentes chat configs/tienda.yaml --thread cliente-42
Tú: ¿Hasta qué hora abren el sábado?
Ferretería El Tornillo: Los sábados atendemos de 8:00 a. m. a 2:00 p. m. (Fuente: horarios.md)
Tú: Envíale a ana@ejemplo.com la política de garantías
Acción pendiente: Enviar correo a ana@ejemplo.com con asunto "Política de garantías"
¿Confirmas? (s/n): s
Ferretería El Tornillo: Listo, el correo quedó enviado.
Tú: salir
¡Hasta pronto!

$ uv run agentes auditoria configs/tienda.yaml
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

## Sector examples

| Config | Company (fictional) | What it shows |
|--------|---------------------|---------------|
| `configs/despacho-juridico.yaml` | Rincón & Asociados Abogados | Colombian legal deadlines (`calcular_plazo`), clause-by-clause contract review, fees FAQ, case intake into the sheet |
| `configs/tienda.yaml` | Ferretería El Tornillo | Opening hours, warranties, delivery rules |
| `configs/clinica.yaml` | Clínica Sol del Valle | Exam preparation, insurers, cancellations; never diagnoses, sends emergencies to 123 |

```
$ uv run agentes chat configs/despacho-juridico.yaml
Tú: ¿Cuándo vence la reposición contra el auto notificado el 18/12/2025?
Rincón & Asociados Abogados: Recurso de reposición (CGP art. 318): 3 días hábiles.
Notificación: 18/12/2025. Corre desde 19/12/2025. Vence el 14/01/2026 (miércoles).
Aplica a providencias dictadas fuera de audiencia; si se dictan en audiencia, el recurso se interpone en ella.
Cálculo orientativo: verifique el expediente, suspensiones y días de cierre extraordinario del despacho.
```

### Colombian legal deadlines (`agentes.legal`)

Pure, exhaustively tested functions; the model only picks the procedural action and the date.

- **Holidays:** fixed dates; Ley 51 de 1983 (*Ley Emiliani*) moves seven of them to Monday;
  Holy Thursday/Friday and three Easter-based holidays moved to Monday.
- **Business days (CGP art. 118):** day terms count business days only, from the day after notification.
- **Judicial vacancy:** 20 December – 10 January and Monday–Wednesday of Holy Week; judicial terms do not run.
- **Personal notification by data message (Ley 2213 de 2022 art. 8):** done once two business days have passed
  after sending (with the C-420 de 2020 caveat about acknowledgement of receipt). It only applies to terms that
  start with a personal notification (answering a claim, exceptions); autos notified by *estado* do not get it.
- **Administrative terms** (derecho de petición, Ley 1755 de 2015 art. 14) skip weekends and holidays but not the judicial vacancy.
- **Catalogue:** reposición (3), apelación de auto/sentencia (3) — for decisions issued outside a hearing —,
  contestación verbal (20) and verbal sumario (10), excepciones en ejecutivo (10), impugnación de tutela (3),
  derecho de petición: general (15), documents/information (10), consultation (30).

Every answer carries a disclaimer: it is an orientative calculation to be checked against the case file.

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
| `tools` | no | Enabled tools: `buscar_documentos`, `registrar_en_hoja`, `enviar_correo`, `calcular_plazo`. |
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
- [x] **Phase 3 — Sector examples:** law firm (Colombian legal deadlines), shop, clinic.
- [ ] **Phase 4 — API & integrations:** FastAPI service, web demo, MCP server, n8n flows and a custom n8n node.
- [ ] **Phase 5 — Presentation:** Docker, demo GIF, final polish.

## License

[MIT](LICENSE)

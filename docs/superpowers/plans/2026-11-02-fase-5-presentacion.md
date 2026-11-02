# Phase 5 — Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo look and behave like the work of an excellent programmer on first contact, then publish it to GitHub.

**Architecture:** No new subsystems. Fix the deferred minors a visitor would notice while trying the demo, polish the READMEs (badges, Docker quickstart, demo GIF, known limitations), run a final review, and publish under `ricardoprs76-max` only after the owner's explicit OK.

**Tech Stack:** existing (Python 3.12/uv, FastAPI, vanilla JS web chat, n8n node); playwright-cli for screenshots; Pillow via `uv run --with pillow` (not a project dependency) to assemble the GIF; `gh` CLI for publishing.

**Spec:** `docs/superpowers/specs/2026-10-30-agentes-ia-empresas-design.md` (Phase 5: "README (EN) + README.es.md with GIF, architecture diagram, badges, Dockerfile polish, final review; publish to GitHub with the owner").

## Global Constraints

- Branch `fase-5-presentacion`; commit author Ricardo Porras <ricardoprs76@gmail.com> (repo-local config), commits keep the `Co-Authored-By: Claude …` trailer.
- GitHub owner is **`ricardoprs76-max`**; repo `agentes-ia-empresas`, **public**, created only after the owner says yes in this session.
- Code and README in English, README.es.md in Spanish, agent and demo data in Spanish.
- READMEs never stress "made with AI" / "desde 2026"; at most a mild "con apoyo de IA" if anything.
- Every check stays green: `ruff check`, `ruff format --check`, `mypy` (strict), `pytest`, node `npm run lint` + `npm test`.
- Demo companies are fictitious and must say so wherever a visitor sees their name.

## Review Focus

1. A visitor asks the law-firm demo for a deadline without naming the actuación → they get told which actuaciones exist, not a silent "reposición" result (Task 1 test).
2. The model asks `calcular_plazo` for an unknown actuación → the tool answer lists the valid options so the model can recover (Task 1 test).
3. Double click on "Confirmar" in the web chat → the 409 shows a Spanish notice and the user's message is not duplicated in the conversation (Task 1 manual check with playwright).
4. A client posts a body that is not UTF-8 → Spanish 400 like every other API error (Task 1 test).
5. A visitor clones and follows the README literally on a clean machine → every command in the Quickstart and Docker sections works as written (Task 2 step: run each non-Docker command; Docker ones are covered by the CI job).

---

### Task 1: Visible fixes

**Files:**
- Modify: `configs/despacho-juridico.yaml`, `configs/tienda.yaml`, `configs/clinica.yaml` (`company_name` gets ` (ficticia)`), `src/agentes/tools/builtin.py` (unknown actuación message), `src/agentes/llm/demo.py` (deadline without actuación), `src/agentes/api/app.py` (Spanish 400 for undecodable bodies), `src/agentes/api/static/*.js` (409 handling).
- Test: `tests/test_tools_legal.py` / `tests/test_demo_model.py` / `tests/test_api.py` (existing files; add to whichever already covers the module).

**Interfaces:** none new; behaviour only.

- [ ] **Step 1: Failing tests**
  - `test_unknown_actuacion_lists_options`: calling the `calcular_plazo` tool with `actuacion="inexistente"` returns text containing `"Opciones"` and `"reposicion"` (no exception).
  - `test_demo_deadline_without_actuacion_asks_which`: demo model, message `"¿cuándo vence el plazo? me notificaron el 3 de marzo de 2026"` → no tool call; reply contains `"apelación"` and `"reposición"`.
  - `test_non_utf8_body_is_spanish_400`: POST `/chat` with bytes `b'{"message": "\xff"}'` → 400 (or 422) whose `detail` is Spanish (contains `"UTF-8"` and no English sentence such as `"There was an error"`).
  - `test_company_names_say_ficticia`: every `configs/*.yaml` `company_name` ends with `(ficticia)`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Tool: catch the validation error for `actuacion` before the generic `_invalid_args` path and return the catalogue keys. Demo: when `_DEADLINE_RE` and a date match but no `_ACTUACIONES` entry matches, answer with the list of actuaciones in Spanish instead of defaulting. API: exception handler for JSON decode errors → `{"detail": "El cuerpo debe ser JSON en UTF-8."}`. Web: on 409 remove the optimistic user bubble and show "Espera: el agente aún está respondiendo." Fix any test that asserted the old company names.
- [ ] **Step 4:** Run all checks → PASS; playwright-cli: double-click "Confirmar" shows the notice once.
- [ ] **Step 5: Commit** `fix: clearer demo, deadline and error messages for visitors`.

### Task 2: README polish and demo GIF

**Files:**
- Modify: `README.md`, `README.es.md`, `pyproject.toml` + `integrations/n8n/node/package.json` + `integrations/n8n/node/credentials/AgentesIaApi.credentials.ts` + `integrations/n8n/node/nodes/AgentesIa/AgentesIa.node.json` (URLs `ricardoprs76` → `ricardoprs76-max`), `.env.example` (comment that `docker compose` requires `AGENTES_API_KEY`).
- Create: `docs/demo.gif` (≤ 3 MB, ~800 px wide), `scripts/` not added — the GIF recipe lives in the ledger, not the repo.

- [ ] **Step 1:** Replace URLs; `grep -rn "github.com/ricardoprs76/"` outside `docs/superpowers` and `node_modules` → no hits; node `npm test` still green.
- [ ] **Step 2:** Badges under the title: CI (`https://github.com/ricardoprs76-max/agentes-ia-empresas/actions/workflows/ci.yml/badge.svg`), Python 3.12, mypy strict, ruff, License MIT.
- [ ] **Step 3:** Quickstart gets a "With Docker" block first (`.env` + `docker compose up --build`, URLs of agent and n8n) and the uv block second.
- [ ] **Step 4:** GIF: serve `configs/despacho-juridico.yaml` in demo mode; playwright-cli screenshots of: greeting → question with cited answer → deadline calculation → email request showing the confirmation card → "Confirmar" → result. Assemble with Pillow (≈1.2 s per frame, last frame 3 s), embed at the top of both READMEs with Spanish/English alt text.
- [ ] **Step 5:** "Known limitations" section (EN + ES): embeddings recomputed at each start; `agentes auditoria` has no `--db`; SMTP over 465 not supported; extra CSV columns ignored; IPv6 `::1` needs a key; `/docs` is public when a key is set; keyword search does not relate "arriendo"/"arrendamiento"; Holy Week vacancy and courts without vacancy as already documented.
- [ ] **Step 6:** Run every non-Docker README command once on this machine; fix any that fails.
- [ ] **Step 7: Commit** `docs: badges, Docker quickstart, demo GIF and known limitations`.

### Task 3: Final review

- [ ] **Step 1:** `/code-review high` over `main..fase-5-presentacion` plus a manual read of the top-level files a visitor opens first (README, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `src/agentes/cli.py`).
- [ ] **Step 2:** Fix confirmed findings; all checks green.
- [ ] **Step 3: Commit** `chore: address final review`; show the owner a summary and ask to merge.
- [ ] **Step 4:** Merge `fase-5-presentacion` into `main` (`--no-ff`), delete the branch.

### Task 4: Publish (only after the owner's explicit yes)

- [ ] **Step 1:** Ask: "¿Publico ahora el repositorio público en github.com/ricardoprs76-max/agentes-ia-empresas?" Stop if not yes.
- [ ] **Step 2:** `gh repo create ricardoprs76-max/agentes-ia-empresas --public --source . --push --description "<one line>"`; add topics `ai-agents, langgraph, fastapi, mcp, n8n, python`.
- [ ] **Step 3:** Watch the first CI run (`gh run watch`); all three jobs (`checks`, `n8n-node`, `docker`) green. A failure is fixed on a branch and merged, never force-pushed.
- [ ] **Step 4:** Open the repo page, check the GIF and badges render; report the URL.

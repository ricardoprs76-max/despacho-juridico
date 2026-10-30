# Phase 3 — Sector Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three ready-to-run sector configs — law firm (flagship), shop, clinic — with fictional Spanish documents, plus a tested Colombian legal-deadline calculator exposed to the law-firm agent as the tool `calcular_plazo`.

**Architecture:** New package `agentes.legal`: `festivos` (Colombian holidays: fixed, Ley 51/1983 "Emiliani" Monday moves, Easter-based), `plazos` (business-day arithmetic under CGP art. 118 with judicial vacancy, optional Ley 2213/2022 electronic-notification offset) and a catalogue of common procedural terms with their legal basis. The tool lives in `agentes.tools` like the others. Configs and demo documents are data only.

**Tech Stack:** Phase 2 stack; stdlib `datetime` only for the legal module.

**Spec:** `docs/superpowers/specs/2026-10-30-agentes-ia-empresas-design.md`

## Global Constraints

- All Phase 1–2 constraints apply (`python -m uv`, ruff + `mypy --strict` + pytest green, `set -o pipefail` on any piped check, English code / Spanish user text, UTF-8, author `Ricardo Porras <ricardoprs76@gmail.com>`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- Legal rules encoded (owner is a Colombian lawyer and reviews them at phase end):
  - Fixed holidays: Jan 1, May 1, Jul 20, Aug 7, Dec 8, Dec 25.
  - Moved to the following Monday (Ley 51 de 1983) unless already Monday: Jan 6, Mar 19, Jun 29, Aug 15, Oct 12, Nov 1, Nov 11.
  - Easter-based: Jueves Santo (E−3), Viernes Santo (E−2) not moved; Ascensión (E+39), Corpus Christi (E+60), Sagrado Corazón (E+68) moved to the following Monday.
  - Judicial vacancy (no judicial terms run): Dec 20 – Jan 10 inclusive, and Holy Week Monday–Wednesday (Thu/Fri are holidays).
  - CGP art. 118: a term in days counts business days only and starts the day after notification.
  - Ley 2213 de 2022 art. 8: personal notification by data message is understood done when two business days have passed after sending; the term starts the next day.
  - Administrative terms (derecho de petición, Ley 1755 de 2015 art. 14: 15 días hábiles) skip weekends and holidays but NOT judicial vacancy.
  - Terms in months/years are out of scope this phase.
- Every deadline answer ends with: `Cálculo orientativo: verifique el expediente, suspensiones y días de cierre extraordinario del despacho.`
- Demo documents are fictional; company names include "(empresa ficticia)" in their documents.

## Review Focus

1. Terms that cross the year boundary and the Dec 20 – Jan 10 vacancy (e.g. notified Dec 18) → vacancy days skipped, holidays of the new year computed for that year (Task 2 test).
2. Notification on a Saturday, holiday or vacancy day → counting still starts with the next business day after it (Task 2 test).
3. Bad tool input — unknown actuación, unparseable or impossible date (`31/02/2026`), date far outside 1900–2100 → one Spanish error line, no exception (Task 3 test).
4. A year where two moved holidays land on the same Monday (2025: San Pedro y San Pablo + Sagrado Corazón on Jun 30) → one date, both names, 17 holiday dates (Task 1 test).
5. Every shipped config loads, its knowledge folder produces no warnings, and a typical question finds the right document (Task 5 test).

---

### Task 1: Colombian holidays

**Files:**
- Create: `src/agentes/legal/__init__.py`, `src/agentes/legal/festivos.py`
- Test: `tests/legal/test_festivos.py`

**Interfaces:**
- Produces:
  - `easter_sunday(year: int) -> date` (anonymous Gregorian algorithm).
  - `festivos(year: int) -> dict[date, str]` — date → Spanish name; names joined with `" / "` when two fall on one date; `functools.cache`d.
  - `es_festivo(day: date) -> bool`.

- [ ] **Step 1: Write failing tests:** `test_easter_known_years` (2024-03-31, 2025-04-20, 2026-04-05, 2027-03-28), `test_festivos_2026_exact` (the 18 dates: 01-01, 01-12, 03-23, 04-02, 04-03, 05-01, 05-18, 06-08, 06-15, 06-29, 07-20, 08-07, 08-17, 10-12, 11-02, 11-16, 12-08, 12-25), `test_festivos_2025_shared_monday` (17 dates; 2025-06-30 name contains both "San Pedro y San Pablo" and "Sagrado Corazón"), `test_holiday_already_monday_not_moved` (2026-06-29, 2026-10-12), `test_names_are_spanish` (2026-08-17 → "La Asunción de la Virgen").
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full suite + checks → PASS.
- [ ] **Step 5: Commit** `feat(legal): add Colombian public holidays`.

### Task 2: Business days and deadlines

**Files:**
- Create: `src/agentes/legal/plazos.py`
- Test: `tests/legal/test_plazos.py`

**Interfaces:**
- Consumes: `es_festivo`, `easter_sunday` (Task 1).
- Produces:
  - `en_vacancia_judicial(day: date) -> bool` — Dec 20–Jan 10 or Mon–Wed of Holy Week.
  - `es_dia_habil(day: date, judicial: bool = True) -> bool` — not Sat/Sun, not holiday, and (if judicial) not vacancy.
  - `siguiente_dia_habil(day: date, judicial: bool = True) -> date` — first business day strictly after `day`.
  - `sumar_dias_habiles(desde: date, dias: int, judicial: bool = True) -> date` — the `dias`-th business day strictly after `desde`; `dias < 1` → `ValueError("El término debe ser de al menos un día.")`.
  - `fecha_notificacion_efectiva(envio: date, judicial: bool = True) -> date` — `sumar_dias_habiles(envio, 2, judicial)` (Ley 2213 art. 8).
  - `@dataclass(frozen=True) class Termino`: `clave: str`, `nombre: str`, `dias: int`, `norma: str`, `judicial: bool = True`.
  - `CATALOGO: dict[str, Termino]` with exactly: `reposicion` (Recurso de reposición, 3, "CGP art. 318"), `apelacion_auto` (Apelación de auto, 3, "CGP art. 322"), `apelacion_sentencia` (Apelación de sentencia, 3, "CGP art. 322"), `contestacion_verbal` (Contestación de demanda en proceso verbal, 20, "CGP art. 369"), `contestacion_verbal_sumario` (Contestación en proceso verbal sumario, 10, "CGP art. 391"), `excepciones_ejecutivo` (Excepciones en proceso ejecutivo, 10, "CGP art. 442"), `impugnacion_tutela` (Impugnación de fallo de tutela, 3, "Decreto 2591 de 1991 art. 31"), `respuesta_derecho_peticion` (Respuesta a derecho de petición, 15, "Ley 1755 de 2015 art. 14", judicial=False).
  - `@dataclass(frozen=True) class ResultadoPlazo`: `termino: Termino`, `notificacion: date`, `inicio: date`, `vencimiento: date`, `electronica: bool`.
  - `calcular_plazo(clave: str, notificacion: date, electronica: bool = False) -> ResultadoPlazo` — unknown key → `KeyError` subclass `PlazoDesconocido` with Spanish message listing valid keys.
  - `ResultadoPlazo.texto() -> str` — Spanish, e.g. `Recurso de reposición (CGP art. 318): 3 días hábiles. Notificación: 02/03/2026. Corre desde 03/03/2026. Vence el 05/03/2026 (jueves).` + (electronic) `Notificación electrónica: se entiende surtida el <dd/mm/yyyy> (Ley 2213 de 2022 art. 8).` + the fixed disclaimer line. Dates `dd/mm/yyyy`, weekday in Spanish.

- [ ] **Step 1: Write failing tests:** `test_weekend_and_holiday_not_business`, `test_vacancy_bounds` (2025-12-19 business; 12-20, 2026-01-10 vacancy; 2026-01-13 business — 01-12 is a holiday), `test_holy_week_vacancy_2026` (03-30, 03-31, 04-01 vacancy; 04-06 business), `test_petition_ignores_vacancy` (es_dia_habil(2025-12-22, judicial=False) is True), `test_three_days_simple` (reposición notified Mon 2026-03-02 → vence Thu 2026-03-05), `test_counting_skips_holiday` (notified Fri 2026-03-20 → 3 days: Tue 03-24, Wed 03-25, Thu 03-26 → vence 03-26; 03-23 holiday), `test_crosses_year_and_vacancy` (notified 2025-12-18, 3 days judicial → 12-19, 2026-01-13, 01-14 → vence 2026-01-14), `test_notified_on_saturday` (2026-03-07 → reposición vence 2026-03-11), `test_electronic_notification_offset` (sent Mon 2026-03-02 → efectiva Wed 03-04; reposición vence Mon 03-09), `test_petition_15_days` (2026-12-14 → 15 business days non-judicial → 2027-01-06? compute: excludes 12-25, 2027-01-01, weekends; and 2027-01-11 Reyes moved — assert the value computed by hand in the test with a comment), `test_zero_days_rejected`, `test_unknown_key_lists_options`, `test_texto_format` (exact string for the reposición example incl. disclaimer).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(legal): add business-day deadline calculator (CGP art. 118)`.

### Task 3: `calcular_plazo` tool

**Files:**
- Modify: `src/agentes/tool_names.py`, `src/agentes/tools/builtin.py`, `src/agentes/llm/demo.py`
- Test: `tests/tools/test_registry.py`, `tests/llm/test_demo.py`

**Interfaces:**
- Consumes: `calcular_plazo`, `CATALOGO`, `PlazoDesconocido` (Task 2).
- Produces:
  - `"calcular_plazo"` added to `TOOL_NAMES` (read-only, not in `SIDE_EFFECT_TOOLS`).
  - Tool args: `actuacion: Literal[<CATALOGO keys>]`, `fecha_notificacion: str` (accepts `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`), `notificacion_electronica: bool = False`. Returns `ResultadoPlazo.texto()`, or one Spanish error line: `Fecha no válida: <value>. Usa el formato DD/MM/AAAA.`, `Fecha fuera de rango: <value>.` (outside 1900–2100), or the unknown-key message. Description lists every key with its nombre.
  - Demo model: when `calcular_plazo` is bound and text matches `\b(plazo|t[ée]rmino|vence|vencimiento)` and contains a date `\d{1,2}/\d{1,2}/\d{4}` or ISO date → call with the first date; actuación by keywords (`reposici` → reposicion, `apelaci` + `sentencia` → apelacion_sentencia, `apelaci` → apelacion_auto, `sumario` → contestacion_verbal_sumario, `contesta` → contestacion_verbal, `excepci` → excepciones_ejecutivo, `tutela` → impugnacion_tutela, `petici` → respuesta_derecho_peticion; default reposicion); `electr` or `correo` in text → `notificacion_electronica=True`.

- [ ] **Step 1: Write failing tests:** `test_plazo_tool_returns_text`, `test_plazo_tool_accepts_three_date_formats`, `test_plazo_tool_bad_date_message` (`31/02/2026`), `test_plazo_tool_out_of_range_message` (`01/01/1800`), `test_plazo_schema_enumerates_actuaciones` (JSON schema `enum` == sorted CATALOGO keys), `test_demo_calls_plazo_tool` (`"¿Cuándo vence la reposición notificada el 02/03/2026?"` → args `{"actuacion": "reposicion", "fecha_notificacion": "02/03/2026", "notificacion_electronica": False}`), `test_demo_plazo_electronic_flag`, `test_demo_plazo_without_date_no_call`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(tools): add calcular_plazo tool for Colombian legal deadlines`.

### Task 4: Sector configs and fictional documents

**Files:**
- Rename: `configs/ejemplo.yaml` → `configs/tienda.yaml` (update `tests/conftest.py::EXAMPLE_CONFIG`, README/README.es quickstart and every reference)
- Create: `configs/despacho-juridico.yaml`, `configs/clinica.yaml`
- Create: `data/demo/despacho/servicios-y-tarifas.md`, `preguntas-frecuentes.md`, `atencion-y-confidencialidad.md`, `modelo-contrato-arrendamiento.md`; `data/demo/clinica/horarios-y-sedes.md`, `preparacion-examenes.md`, `convenios-y-pagos.md`, `cancelaciones.md`
- Test: `tests/test_configs.py`

**Interfaces:**
- Produces:
  - `despacho-juridico.yaml`: id `despacho-juridico`, company `Rincón & Asociados Abogados` (fictional), sector `despacho jurídico`, formal tone; rules: no guaranteed outcomes; legal advice only after a lawyer reviews the case; always mention deadlines are orientative; never ask for or repeat full ID numbers in email; for contract review point out clause by clause risks citing the clause number. Tools: `buscar_documentos`, `calcular_plazo`, `registrar_en_hoja`, `enviar_correo`; confirm both side-effect tools.
  - `clinica.yaml`: id `clinica`, `Clínica Sol del Valle` (fictional), sector `salud`; rules: never diagnose or recommend medication; emergencies → line 123 immediately; collect name + phone + preferred date for appointment requests and register them; don't store medical history details. Tools: `buscar_documentos`, `registrar_en_hoja`, `enviar_correo` (both confirmed).
  - `tienda.yaml`: current ferretería content unchanged.
- [ ] **Step 1: Write failing tests** (parametrized over `configs/*.yaml`): `test_config_loads`, `test_knowledge_has_no_warnings` (build_context with env={} → warnings == ()), `test_typical_question_finds_document` (table: tienda `"¿hacen domicilios?"` → `domicilios.md`; despacho `"¿cuánto cuesta la consulta?"` → `servicios-y-tarifas.md`; clinica `"¿cómo me preparo para el examen de sangre?"` → `preparacion-examenes.md`), `test_despacho_enables_calcular_plazo`, `test_exactly_three_configs`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Write configs and documents (the contract model has numbered clauses incl. one abusive-looking clause, e.g. a penalty of 10 monthly rents, so a clause review has something to flag). **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(configs): add law firm and clinic examples; rename shop config`.

### Task 5: Phase 3 docs

**Files:**
- Modify: `README.md`, `README.es.md`, `docs/architecture.md`

- [ ] **Step 1:** Add "Sector examples" section (EN/ES): table of the three configs (what each shows), a law-firm transcript using `calcular_plazo`, the legal rules encoded (bullet list mirroring Global Constraints) with the disclaimer; quickstart uses `configs/tienda.yaml`; tick Phase 3. Architecture: add `agentes.legal` row and decision "legal rules as pure, exhaustively tested functions; the model only chooses the actuación and date".
- [ ] **Step 2:** All checks green. **Step 3: Commit** `docs: document sector examples and legal deadlines`.
- [ ] **Step 4:** Summarize Phase 3 to the owner in Spanish — explicitly ask her, as a lawyer, to verify the encoded rules and the catalogue — and wait for approval before Phase 4.

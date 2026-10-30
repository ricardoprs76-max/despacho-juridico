# Agentes IA para Empresas

> [Read in English](README.md)

**Un motor, muchas empresas.** Describe una empresa en un solo archivo YAML (nombre,
sector, tono y reglas) y obtén un agente de IA que conversa en español y recuerda cada
conversación, construido con [LangGraph](https://github.com/langchain-ai/langgraph).
Cambia el archivo y el mismo motor atiende a un despacho jurídico, una ferretería o una clínica.

- **Cualquier proveedor:** Google Gemini (gratis), Anthropic Claude u OpenAI, según la configuración.
- **Funciona sin claves:** sin clave de IA arranca en *modo demo*, claramente señalado,
  para que cualquiera lo pruebe en un minuto.
- **Memoria persistente:** cada conversación se guarda en SQLite y sobrevive a reinicios.
- **Calidad exigente:** `mypy --strict`, `ruff` y pruebas que nunca llaman a una IA real,
  ejecutadas en CI en Linux y Windows.

## Inicio rápido

```bash
pip install uv            # si no lo tienes
uv sync
uv run agentes validate configs/ejemplo.yaml
uv run agentes chat configs/ejemplo.yaml
```

Para usar un modelo real, copia `.env.example` a `.env` (o exporta la variable) y define
`GOOGLE_API_KEY`; basta una clave gratuita de [Google AI Studio](https://aistudio.google.com/apikey).
`ANTHROPIC_API_KEY` y `OPENAI_API_KEY` funcionan igual. Escribe `salir` para terminar.

## Configuración de la empresa

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `id` | sí | Identificador (`a-z`, `0-9`, `-`). |
| `company_name` | sí | Nombre que aparece en las respuestas. |
| `sector` | sí | Sector, p. ej. `despacho jurídico`. |
| `tone` | sí | Cómo debe sonar el agente. |
| `rules` | no | Reglas que el agente debe cumplir. |
| `model.provider` | no | `gemini` (por defecto), `anthropic` u `openai`. |
| `model.model` | no | Nombre del modelo; hay uno por defecto para cada proveedor. |
| `model.temperature` | no | De `0` a `1`; por defecto `0.2`. |
| `tools`, `confirm_tools` | no | Herramientas activas y las que piden confirmación (Fase 2). |
| `knowledge_dir` | no | Carpeta con los documentos de la empresa (Fase 2). |

## Hoja de ruta

- [x] **Fase 1 — Núcleo:** configuración, elección de modelo con modo demo, agente LangGraph con memoria, CLI.
- [ ] **Fase 2 — Herramientas y seguridad:** consulta de documentos con citas, Sheets y correo, confirmación humana, registro de auditoría.
- [ ] **Fase 3 — Ejemplos por sector:** despacho jurídico (plazos legales colombianos), tienda, clínica.
- [ ] **Fase 4 — API e integraciones:** servicio FastAPI, demo web, servidor MCP, flujos y nodo propio de n8n.
- [ ] **Fase 5 — Presentación:** Docker, GIF de demostración, pulido final.

## Licencia

[MIT](LICENSE)

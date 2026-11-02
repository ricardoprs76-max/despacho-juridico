# n8n-nodes-agentes-ia

n8n node for [Agentes IA para Empresas](../../../README.md): send messages to a company's
AI agent, approve or cancel the actions it is waiting on, and read its audit log — from any
n8n workflow.

The agent's safety rules travel with it: an action with side effects (sending an email,
writing a sheet row) never runs from a single call. **Send Message** returns it in `pending`
and it runs only after **Confirm** with `approve = true`.

## Operations

| Resource | Operation | API call |
|----------|-----------|----------|
| Conversation | Send Message | `POST /chat` → `{thread_id, reply, pending}` |
| Conversation | Confirm | `POST /chat/{thread_id}/confirm` |
| Conversation | Get History | `GET /chat/{thread_id}` |
| Audit | Get Many | `GET /audit?thread_id=&limit=` (one item per entry) |

Thread IDs accept letters, numbers, `-` and `_` (up to 64 characters). The node can also be
used as a tool by n8n's AI Agent node.

## Credentials

**Agentes IA API**: the agent server's **Base URL** (`http://localhost:8000`, or
`http://agente:8000` inside the project's docker-compose) and the **API Key** set in
`AGENTES_API_KEY` on that server (empty if it has none). n8n tests it against `GET /health`.

## Install

In a self-hosted n8n, build the package and point n8n at it:

```bash
npm ci
npm run build
N8N_CUSTOM_EXTENSIONS="$(pwd)" npx n8n
```

The project's `docker-compose.yml` builds an n8n image with the node already installed.

## Development

```bash
npm run lint   # official n8n community-node rules (strict)
npm test       # build + checks of the node and credential against the API contract
```

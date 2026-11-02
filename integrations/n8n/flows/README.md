# n8n flow templates

Three ready-to-import workflows that connect the agent to real channels. They use the
custom **Agentes IA para Empresas** node (`../node`), so the agent keeps its own rules,
tools and confirmation step — n8n only moves messages in and out.

| File | Trigger | What it does |
|------|---------|--------------|
| `correo-a-agente.json` | New email (IMAP) | Sends subject + body to the agent (one conversation per sender). If the agent wants to act, logs the row as **Pendiente de aprobación** in Google Sheets and does **not** reply; otherwise logs **Respondido** and emails the answer back. |
| `whatsapp-a-agente.json` | WhatsApp Business message | Ignores non-text updates, sends the text to the agent (one conversation per phone). Replies with the answer, or with "Tu solicitud quedó pendiente de aprobación…" when an action is waiting. |
| `aprobar-accion.json` | `GET /webhook/aprobar?conversacion=<id>&aprobar=si\|no` | Approves (`si`) or cancels (anything else) the pending action of that conversation and shows the agent's reply as plain text. |

Conversation ids are built from the sender as `correo-<address>` / `wa-<phone>`, with every
character outside `A-Z a-z 0-9 _ -` replaced by `-` and cut to 64 characters, e.g.
`ana.perez+ventas@ejemplo.com` → `correo-ana-perez-ventas-ejemplo-com`. That is the id the
approval link expects (it is also in the sheet's `Conversación` column).

## Node type

The flows reference the node as `CUSTOM.agentesIa`: that is the name n8n gives to nodes loaded
from a folder (`N8N_CUSTOM_EXTENSIONS`, which is how `docker-compose.yml` and the n8n image in
`../Dockerfile` install it). If the package is instead installed from npm as a community node,
n8n names it `n8n-nodes-agentes-ia.agentesIa`; replace that string in the JSON before importing.

## Credentials to create in n8n

The files reference credentials **by name only** (no ids, no secrets). Create them with
these names, or pick your own in each node after importing:

| Name | Type | Used by |
|------|------|---------|
| `Agentes IA API` | Agentes IA API (base URL + `AGENTES_API_KEY`) | all three |
| `Buzón de la empresa (IMAP)` | IMAP | email |
| `Correo de la empresa (SMTP)` | SMTP | email |
| `Google Sheets` | Google Sheets OAuth2 | email |
| `WhatsApp Business (trigger)` / `WhatsApp Business` | WhatsApp OAuth / WhatsApp API | WhatsApp |
| `Aprobadores` | Basic Auth | approval |

The approval webhook is protected with Basic Auth on purpose: conversation ids are derived
from public data (an email address or phone number), so the link alone must not be enough to
approve an action.

## Import

1. Install the node (see `../node/README.md`) or run `docker compose up` from the repo root.
2. In n8n: **Workflows → Import from File** and choose a JSON file
   (or `n8n import:workflow --input=integrations/n8n/flows/correo-a-agente.json`).
3. Open each node with a warning, select the credential, and for the email flow paste the
   URL of your Google Sheet (tab `Correos`, columns `Fecha, Remitente, Asunto, Estado,
   Detalle, Conversación`).
4. Activate the workflow.

The structure of these files is checked by `tests/test_n8n_flows.py` (valid connections,
no embedded secrets, valid conversation ids, both outcomes of the "pending action" check
handled).

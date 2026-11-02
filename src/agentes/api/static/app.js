// Web chat for one company's agent. A plain client of the HTTP API; every piece of
// text from the agent or the user is inserted with textContent, never as HTML.
"use strict";

const TOOL_LABELS = {
  buscar_documentos: "Buscar en sus documentos",
  calcular_plazo: "Calcular plazos procesales",
  registrar_en_hoja: "Registrar en la hoja",
  enviar_correo: "Enviar correos",
};
const ACTION_LABELS = {
  buscar_documentos: "Búsqueda en documentos",
  calcular_plazo: "Cálculo de plazo",
  registrar_en_hoja: "Registro en la hoja",
  enviar_correo: "Correo",
};
const STATUS_LABELS ={ executed: "Ejecutada", rejected: "Cancelada", error: "Error" };
const THREAD_KEY = "agentes.thread";
const API_KEY = "agentes.key";

const $ = (id) => document.getElementById(id);
const els = {
  mark: $("mark"), company: $("company"), sector: $("sector"), mode: $("mode"),
  tools: $("tools"), keyForm: $("key-form"), keyInput: $("key-input"),
  threadLabel: $("thread-label"), messages: $("messages"), empty: $("empty"),
  status: $("status"), composer: $("composer"), message: $("message"), send: $("send"),
  ledger: $("ledger"), ledgerEmpty: $("ledger-empty"), newThread: $("new-thread"),
};

const state = { company: "Agente", thread: null, busy: false };

function store(kind) {
  try { return kind === "session" ? window.sessionStorage : window.localStorage; }
  catch { return null; }
}
function read(kind, key) {
  try { return store(kind)?.getItem(key) ?? null; } catch { return null; }
}
function write(kind, key, value) {
  try {
    const s = store(kind);
    if (!s) return;
    if (value === null) s.removeItem(key); else s.setItem(key, value);
  } catch { /* storage blocked: the page keeps working for this visit */ }
}

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function api(method, path, body) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const key = read("session", API_KEY);
  if (key) headers["X-API-Key"] = key;
  let response;
  try {
    response = await fetch(path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "No hay conexión con el servidor.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "La solicitud no es válida.";
    if (response.status === 401) els.keyForm.hidden = false;
    throw new ApiError(response.status, detail);
  }
  return data;
}

function setStatus(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("error", isError);
}

function setBusy(busy) {
  state.busy = busy;
  els.send.disabled = busy;
  els.message.disabled = busy;
}

function setThread(id) {
  state.thread = id;
  write("local", THREAD_KEY, id);
  els.threadLabel.textContent = id ? `Conversación ${id.slice(0, 8)}` : "Nueva";
}

function scrollDown() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function addMessage(role, text) {
  els.empty.hidden = true;
  const item = node("li", `msg ${role}`);
  const who = role === "user" ? "Tú" : role === "assistant" ? state.company : "Aviso";
  item.append(node("span", "who", who), node("p", "text", text));
  els.messages.append(item);
  scrollDown();
  return item;
}

function draftRows(pending) {
  const a = pending.args || {};
  if (pending.tool === "enviar_correo") {
    return [["Acción", "Enviar correo"], ["Para", a.para], ["Asunto", a.asunto], ["Texto", a.cuerpo]];
  }
  if (pending.tool === "registrar_en_hoja" && Array.isArray(a.datos)) {
    return [["Acción", "Registrar en la hoja"],
      ...a.datos.map((d) => [String(d.campo ?? ""), String(d.valor ?? "")])];
  }
  return [["Acción", pending.description]];
}

function showPending(pending) {
  els.empty.hidden = true;
  const item = document.getElementById("pending-template").content.firstElementChild.cloneNode(true);
  const dl = item.querySelector(".draft");
  for (const [term, value] of draftRows(pending)) {
    dl.append(node("dt", "", term), node("dd", "", value ?? "—"));
  }
  const buttons = item.querySelectorAll("button");
  for (const button of buttons) {
    button.addEventListener("click", () => {
      for (const b of buttons) b.disabled = true;
      answer(button.dataset.approve === "true", item);
    });
  }
  els.messages.append(item);
  setBusy(true);
  els.send.disabled = true;
  setStatus("El agente espera tu decisión sobre esta acción.");
  scrollDown();
  buttons[0].focus();
}

function showReply(data) {
  setThread(data.thread_id);
  if (data.pending) { showPending(data.pending); return; }
  if (data.reply) addMessage("assistant", data.reply);
  setStatus("");
  setBusy(false);
}

async function sendMessage() {
  const text = els.message.value.trim();
  if (!text || state.busy) return;
  setBusy(true);
  const bubble = addMessage("user", text);
  els.message.value = "";
  setStatus("Pensando…");
  try {
    const body = state.thread ? { message: text, thread_id: state.thread } : { message: text };
    showReply(await api("POST", "/chat", body));
  } catch (error) {
    // The server keeps no trace of a failed turn: take the message back so it can be resent.
    bubble.remove();
    if (!els.messages.children.length) els.empty.hidden = false;
    els.message.value = text;
    setStatus(error.message, true);
    setBusy(false);
  }
  refreshAudit();
}

async function answer(approved, card) {
  setStatus(approved ? "Ejecutando la acción…" : "Cancelando la acción…");
  try {
    const data = await api("POST", `/chat/${state.thread}/confirm`, { approved });
    card.classList.add("done");
    card.querySelector(".pending-actions").replaceChildren(
      node("p", "note", approved ? "Aprobada por ti." : "Cancelada por ti."),
    );
    showReply(data);
  } catch (error) {
    setStatus(error.message, true);
    if (error.status === 409) { card.remove(); setBusy(false); }
    else for (const b of card.querySelectorAll("button")) b.disabled = false;
  }
  refreshAudit();
}

function formatTime(iso) {
  const date = new Date(iso);
  return date.toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function auditDetail(entry) {
  const a = entry.args || {};
  if (entry.tool === "enviar_correo") return `Para ${a.para ?? "—"}: ${a.asunto ?? ""}`;
  if (entry.tool === "buscar_documentos") return `Búsqueda: ${a.consulta ?? ""}`;
  if (entry.tool === "calcular_plazo") return `${a.actuacion ?? ""}, notificación ${a.fecha_notificacion ?? ""}`;
  if (entry.tool === "registrar_en_hoja" && Array.isArray(a.datos)) {
    return a.datos.map((d) => `${d.campo}: ${d.valor}`).join(", ");
  }
  return entry.result;
}

async function refreshAudit() {
  if (!state.thread) { renderAudit([]); return; }
  try {
    renderAudit(await api("GET", `/audit?thread_id=${encodeURIComponent(state.thread)}&limit=20`));
  } catch { /* the chat already shows the error */ }
}

function renderAudit(entries) {
  els.ledger.replaceChildren();
  els.ledgerEmpty.hidden = entries.length > 0;
  for (const entry of entries) {
    const item = node("li");
    const row = node("div", "row1");
    row.append(node("span", "tool", ACTION_LABELS[entry.tool] ?? entry.tool),
      node("span", "when", formatTime(entry.timestamp)));
    item.append(row, node("span", `pill ${entry.status}`, STATUS_LABELS[entry.status] ?? entry.status),
      node("p", "detail", auditDetail(entry)));
    els.ledger.append(item);
  }
}

function initials(name) {
  const words = name.split(/\s+/).filter((w) => /^\p{L}/u.test(w) && !/^(el|la|los|las|de|del|y)$/i.test(w));
  return (words.slice(0, 2).map((w) => w[0]).join("") || "A").toUpperCase();
}

function renderHealth(health) {
  state.company = health.company;
  document.title = `${health.company} · Agente`;
  els.company.textContent = health.company;
  els.sector.textContent = health.fictitious ? `${health.sector} · empresa ficticia de ejemplo` : health.sector;
  els.mark.textContent = initials(health.company);
  els.mode.textContent = health.demo ? "Modo demo: respuestas de ejemplo" : `${health.provider} · ${health.model}`;
  els.mode.classList.toggle("demo", health.demo);
  els.tools.replaceChildren(...health.tools.map((tool) => {
    const item = node("li");
    item.append(node("span", "", TOOL_LABELS[tool.name] ?? tool.name));
    if (tool.confirm) item.append(node("span", "ask", "Pide tu sí"));
    return item;
  }));
  els.keyForm.hidden = !health.auth || Boolean(read("session", API_KEY));
}

async function loadThread() {
  const saved = read("local", THREAD_KEY);
  if (!saved) return;
  try {
    const data = await api("GET", `/chat/${encodeURIComponent(saved)}`);
    setThread(data.thread_id);
    for (const m of data.messages) addMessage(m.role, m.text);
    if (data.pending) showPending(data.pending);
    refreshAudit();
  } catch (error) {
    if (error.status === 422) setThread(null);
    else setStatus(error.message, true);
  }
}

function newThread() {
  setThread(null);
  els.messages.replaceChildren();
  els.empty.hidden = false;
  renderAudit([]);
  setStatus("");
  setBusy(false);
  els.message.focus();
}

els.composer.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
els.message.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendMessage();
  }
});
els.newThread.addEventListener("click", newThread);
els.keyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  write("session", API_KEY, els.keyInput.value.trim() || null);
  els.keyInput.value = "";
  els.keyForm.hidden = true;
  setStatus("Clave guardada para esta pestaña.");
  loadThread();
});

(async function start() {
  try {
    renderHealth(await api("GET", "/health"));
  } catch (error) {
    setStatus(error.message, true);
    return;
  }
  await loadThread();
})();

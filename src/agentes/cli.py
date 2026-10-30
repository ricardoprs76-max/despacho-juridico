"""Command-line interface: validate a config, chat with its agent, read the audit log."""

import io
import json
import os
import sqlite3
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from agentes.agent import Agent, AgentError, AgentReply
from agentes.audit import AuditLog, AuditStatus
from agentes.config import AgentConfig, ConfigError, load_config
from agentes.llm import build_chat_model

app = typer.Typer(help="Agentes IA para Empresas", no_args_is_help=True)

EXIT_WORD = "salir"
DEMO_NOTICE = "Modo demo: no hay clave de IA configurada. Las respuestas son de ejemplo."
GOODBYE = "¡Hasta pronto!"
DEFAULT_DATA = Path(".agentes")
MEMORY_FILE = "memoria.sqlite"
YES = {"s", "si", "sí"}
NO = {"n", "no"}
API_KEY_VAR = "AGENTES_API_KEY"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
PUBLIC_WITHOUT_KEY = "Sin AGENTES_API_KEY solo se permite --host 127.0.0.1 o localhost."
STATUS_ES: dict[AuditStatus, str] = {
    "executed": "ejecutada",
    "rejected": "cancelada",
    "error": "error",
}

ConfigArg = Annotated[Path, typer.Argument(help="Archivo YAML de la empresa.")]
DataOpt = Annotated[
    Path | None,
    typer.Option(
        help="Carpeta de datos: memoria, bandeja de salida y hoja (por defecto .agentes)."
    ),
]


class _EndOfInput(Exception):
    """The user closed the input (EOF or Ctrl+C)."""


@app.callback()
def _main() -> None:
    """Agentes IA para Empresas."""
    # API keys may live in a .env file in the current folder; real env vars win.
    load_dotenv(Path.cwd() / ".env")


def _force_utf8() -> None:
    # Windows consoles default to a legacy code page; Spanish text needs UTF-8.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def _load_or_exit(path: Path) -> AgentConfig:
    try:
        return load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _paths(data: Path | None, db: Path | None) -> tuple[Path, Path]:
    """Resolve (data_dir, db_path); an explicit --db alone keeps its folder as data dir."""
    if data is None:
        data = db.parent if db is not None else DEFAULT_DATA
    return data, db if db is not None else data / MEMORY_FILE


def _read(prompt: str) -> str:
    typer.echo(prompt, nl=False)
    try:
        return input()
    except (EOFError, KeyboardInterrupt) as exc:
        typer.echo()
        raise _EndOfInput from exc


def _show(agent: Agent, thread: str, reply: AgentReply) -> None:
    """Print a reply, asking for confirmation as long as an action is pending."""
    while reply.pending is not None:
        typer.echo(f"Acción pendiente: {reply.pending.description}")
        while True:
            answer = _read("¿Confirmas? (s/n): ").strip().lower()
            if answer in YES or answer in NO:
                break
        reply = agent.confirm(thread, approved=answer in YES)
    if reply.text:
        typer.echo(f"{agent.config.company_name}: {reply.text}")


def _guarded(action: Callable[[], AgentReply], agent: Agent, thread: str) -> None:
    """Run one exchange and show it; a model failure is reported and the chat goes on."""
    try:
        _show(agent, thread, action())
    except AgentError as exc:
        typer.echo(f"No se pudo obtener respuesta del modelo: {exc}", err=True)


@app.command()
def validate(config: ConfigArg) -> None:
    """Comprueba que el archivo de configuración es válido."""
    _force_utf8()
    cfg = _load_or_exit(config)
    typer.echo(f"Configuración válida: {cfg.company_name} ({cfg.sector})")


@app.command()
def chat(
    config: ConfigArg,
    thread: Annotated[str, typer.Option(help="Identificador de la conversación.")] = "default",
    data: DataOpt = None,
    db: Annotated[Path | None, typer.Option(help="Archivo SQLite de la memoria.")] = None,
) -> None:
    """Conversa con el agente de la empresa. Escribe 'salir' para terminar."""
    _force_utf8()
    cfg = _load_or_exit(config)
    data_dir, db_path = _paths(data, db)
    with Agent(cfg, build_chat_model(cfg.model), db_path=db_path, data_dir=data_dir) as agent:
        if agent.is_demo:
            typer.echo(DEMO_NOTICE)
        for warning in agent.warnings:
            typer.echo(f"Aviso: {warning}")
        try:
            pending = agent.pending(thread)
            if pending is not None:
                _guarded(partial(AgentReply, text="", pending=pending), agent, thread)
            while True:
                text = _read("Tú: ").strip()
                if not text:
                    continue
                if text.lower() == EXIT_WORD:
                    break
                _guarded(partial(agent.ask, thread, text), agent, thread)
        except (_EndOfInput, KeyboardInterrupt):
            typer.echo()
    typer.echo(GOODBYE)


@app.command()
def serve(
    config: ConfigArg,
    host: Annotated[str, typer.Option(help="Dirección en la que escucha el servidor.")] = (
        "127.0.0.1"
    ),
    port: Annotated[int, typer.Option(help="Puerto del servidor.")] = 8000,
    data: DataOpt = None,
) -> None:
    """Sirve el agente por HTTP (API y chat web). La clave se lee de AGENTES_API_KEY."""
    import uvicorn

    from agentes.api import create_app

    _force_utf8()
    cfg = _load_or_exit(config)
    api_key = os.environ.get(API_KEY_VAR, "").strip() or None
    if api_key is None and host not in LOCAL_HOSTS:
        typer.echo(PUBLIC_WITHOUT_KEY, err=True)
        raise typer.Exit(code=2)
    data_dir, db_path = _paths(data, None)
    with Agent(cfg, build_chat_model(cfg.model), db_path=db_path, data_dir=data_dir) as agent:
        if agent.is_demo:
            typer.echo(DEMO_NOTICE)
        for warning in agent.warnings:
            typer.echo(f"Aviso: {warning}")
        typer.echo(f"Abre http://{host}:{port} en el navegador.")
        uvicorn.run(create_app(agent, api_key), host=host, port=port)


@app.command("mcp")
def mcp_server(config: ConfigArg, data: DataOpt = None) -> None:
    """Sirve el agente como servidor MCP por stdio (para Claude Desktop y otros clientes)."""
    from agentes.mcp import build_mcp_server

    _force_utf8()
    cfg = _load_or_exit(config)
    data_dir, db_path = _paths(data, None)
    with Agent(cfg, build_chat_model(cfg.model), db_path=db_path, data_dir=data_dir) as agent:
        # stdout carries the MCP protocol; every human notice goes to stderr.
        if agent.is_demo:
            typer.echo(DEMO_NOTICE, err=True)
        for warning in agent.warnings:
            typer.echo(f"Aviso: {warning}", err=True)
        build_mcp_server(agent).run("stdio")


@app.command()
def auditoria(
    config: ConfigArg,
    thread: Annotated[str | None, typer.Option(help="Solo esta conversación.")] = None,
    limit: Annotated[int, typer.Option(help="Número máximo de acciones.")] = 20,
    data: DataOpt = None,
) -> None:
    """Muestra las acciones que ha ejecutado, cancelado o intentado el agente."""
    _force_utf8()
    _load_or_exit(config)
    _, db_path = _paths(data, None)
    if not db_path.exists():
        typer.echo("No hay acciones registradas.")
        return
    conn = sqlite3.connect(db_path)
    try:
        entries = AuditLog(conn).entries(thread_id=thread, limit=limit)
    finally:
        conn.close()
    if not entries:
        typer.echo("No hay acciones registradas.")
    for e in entries:
        when = e.timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
        args = json.dumps(e.args, ensure_ascii=False)
        typer.echo(f"{when} | {e.thread_id} | {e.tool} | {STATUS_ES[e.status]} | {args}")

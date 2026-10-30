"""Command-line interface: validate a company config and chat with its agent."""

import io
import sys
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from agentes.agent import Agent, AgentError
from agentes.config import AgentConfig, ConfigError, load_config
from agentes.llm import build_chat_model

app = typer.Typer(help="Agentes IA para Empresas", no_args_is_help=True)

EXIT_WORD = "salir"
DEMO_NOTICE = "Modo demo: no hay clave de IA configurada. Las respuestas son de ejemplo."
GOODBYE = "¡Hasta pronto!"
DEFAULT_DB = Path(".agentes/memoria.sqlite")


@app.callback()
def _main() -> None:
    """Agentes IA para Empresas."""
    # API keys may live in a .env file in the current folder; real env vars win.
    load_dotenv(Path.cwd() / ".env")


ConfigArg = Annotated[Path, typer.Argument(help="Archivo YAML de la empresa.")]


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
    db: Annotated[Path, typer.Option(help="Archivo SQLite de la memoria.")] = DEFAULT_DB,
) -> None:
    """Conversa con el agente de la empresa. Escribe 'salir' para terminar."""
    _force_utf8()
    cfg = _load_or_exit(config)
    with Agent(cfg, build_chat_model(cfg.model), db_path=db) as agent:
        if agent.is_demo:
            typer.echo(DEMO_NOTICE)
        while True:
            typer.echo("Tú: ", nl=False)
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                typer.echo()
                break
            text = line.strip()
            if not text:
                continue
            if text.lower() == EXIT_WORD:
                break
            try:
                reply = agent.ask(thread, text)
            except AgentError as exc:
                typer.echo(f"No se pudo obtener respuesta del modelo: {exc}", err=True)
                continue
            typer.echo(f"{cfg.company_name}: {reply.text}")
    typer.echo(GOODBYE)

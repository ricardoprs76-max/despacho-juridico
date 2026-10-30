import sqlite3
from datetime import UTC
from pathlib import Path

from agentes.audit import AuditLog


def open_log(path: Path) -> tuple[sqlite3.Connection, AuditLog]:
    conn = sqlite3.connect(path)
    return conn, AuditLog(conn)


def test_record_and_read_back(tmp_path: Path) -> None:
    conn, log = open_log(tmp_path / "a.sqlite")
    entry = log.record("t1", "enviar_correo", {"para": "a@b.co"}, "executed", "Correo enviado.")
    [read] = log.entries()
    assert read == entry
    assert read.tool == "enviar_correo"
    assert read.args == {"para": "a@b.co"}
    assert read.status == "executed"
    assert read.timestamp.tzinfo is UTC
    conn.close()


def test_entries_newest_first_and_limit(tmp_path: Path) -> None:
    conn, log = open_log(tmp_path / "a.sqlite")
    for n in range(5):
        log.record("t1", f"tool{n}", {}, "executed", "ok")
    entries = log.entries(limit=3)
    assert [e.tool for e in entries] == ["tool4", "tool3", "tool2"]
    conn.close()


def test_filter_by_thread(tmp_path: Path) -> None:
    conn, log = open_log(tmp_path / "a.sqlite")
    log.record("a", "x", {}, "executed", "ok")
    log.record("b", "y", {}, "rejected", "cancelada")
    assert [e.tool for e in log.entries(thread_id="b")] == ["y"]
    conn.close()


def test_accented_args_round_trip(tmp_path: Path) -> None:
    conn, log = open_log(tmp_path / "a.sqlite")
    log.record("t1", "registrar_en_hoja", {"nota": "señora Peña, ¿mañana?"}, "error", "falló")
    assert log.entries()[0].args == {"nota": "señora Peña, ¿mañana?"}
    raw = conn.execute("SELECT args FROM audit_log").fetchone()[0]
    assert "señora" in raw
    conn.close()


def test_survives_reopen(tmp_path: Path) -> None:
    conn, log = open_log(tmp_path / "a.sqlite")
    log.record("t1", "x", {}, "executed", "ok")
    conn.commit()
    conn.close()
    conn, log = open_log(tmp_path / "a.sqlite")
    assert len(log.entries()) == 1
    conn.close()


def test_has_no_update_or_delete_methods() -> None:
    assert not any(name in dir(AuditLog) for name in ("update", "delete", "clear"))

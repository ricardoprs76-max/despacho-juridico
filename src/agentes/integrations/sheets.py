"""Where 'registrar_en_hoja' writes: a local CSV by default, Google Sheets if configured."""

import csv
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


class SheetBackend(Protocol):
    def append_row(self, values: Mapping[str, str]) -> str: ...


_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _safe(text: str) -> str:
    """Stop spreadsheet apps from running a cell as a formula (CSV injection)."""
    return "'" + text if text.startswith(_FORMULA_START) else text


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class CsvSheet:
    """A CSV file that Excel opens with accents intact (UTF-8 with BOM)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append_row(self, values: Mapping[str, str]) -> str:
        row = {"fecha": _now()}
        for key, value in values.items():
            name = "fecha_dato" if str(key) == "fecha" else _safe(str(key))
            row[name] = _safe(str(value))
        rows: list[dict[str, str]] = []
        header: list[str] = []
        if self.path.exists():
            with self.path.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                header = list(reader.fieldnames or [])
                rows = list(reader)
        header += [key for key in row if key not in header]
        rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, restval="")
            writer.writeheader()
            writer.writerows(rows)
        return f"Fila registrada en {self.path.name}."


class GoogleSheet:
    """Appends to the first worksheet of a Google Sheet via a service account."""

    def __init__(self, sheet_id: str, service_account_file: Path, client: Any = None) -> None:
        self.sheet_id = sheet_id
        self.service_account_file = service_account_file
        self._client = client

    def append_row(self, values: Mapping[str, str]) -> str:
        if self._client is None:
            import gspread

            self._client = gspread.service_account(filename=str(self.service_account_file))
        worksheet = self._client.open_by_key(self.sheet_id).sheet1
        # Free-form rows: each cell is "key: value" so no fixed header is needed.
        cells = [_now(), *(_safe(f"{k}: {v}") for k, v in values.items())]
        worksheet.append_row(cells, value_input_option="RAW")
        return "Fila registrada en Google Sheets."


def sheet_from_env(data_dir: Path, env: Mapping[str, str] | None = None) -> SheetBackend:
    env = os.environ if env is None else env
    account = env.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    sheet_id = env.get("AGENTES_SHEET_ID", "").strip()
    if account and sheet_id:
        return GoogleSheet(sheet_id, Path(account))
    return CsvSheet(data_dir / "hoja.csv")

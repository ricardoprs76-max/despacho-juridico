import csv
from pathlib import Path
from typing import Any

from agentes.integrations import CsvSheet, GoogleSheet, sheet_from_env


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_csv_writes_header_and_rows(tmp_path: Path) -> None:
    sheet = CsvSheet(tmp_path / "hoja.csv")
    assert sheet.append_row({"cliente": "Ana", "pedido": "42"}) == "Fila registrada en hoja.csv."
    sheet.append_row({"cliente": "Luis", "pedido": "43"})
    rows = read_rows(tmp_path / "hoja.csv")
    assert [r["cliente"] for r in rows] == ["Ana", "Luis"]
    assert list(rows[0]) == ["fecha", "cliente", "pedido"]
    assert rows[0]["fecha"].endswith("+00:00")


def test_csv_new_column_extends_header(tmp_path: Path) -> None:
    sheet = CsvSheet(tmp_path / "hoja.csv")
    sheet.append_row({"cliente": "Ana"})
    sheet.append_row({"cliente": "Luis", "telefono": "300"})
    rows = read_rows(tmp_path / "hoja.csv")
    assert list(rows[0]) == ["fecha", "cliente", "telefono"]
    assert rows[0]["telefono"] == ""
    assert rows[1]["telefono"] == "300"


def test_csv_accents_excel_bom(tmp_path: Path) -> None:
    CsvSheet(tmp_path / "hoja.csv").append_row({"nota": "Peña, ¿mañana?"})
    raw = (tmp_path / "hoja.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert read_rows(tmp_path / "hoja.csv")[0]["nota"] == "Peña, ¿mañana?"


def test_csv_creates_parent_folder(tmp_path: Path) -> None:
    CsvSheet(tmp_path / "nueva" / "hoja.csv").append_row({"a": "1"})
    assert (tmp_path / "nueva" / "hoja.csv").exists()


def test_sheet_from_env_defaults_to_csv(tmp_path: Path) -> None:
    sheet = sheet_from_env(tmp_path, env={})
    assert isinstance(sheet, CsvSheet)
    assert sheet.path == tmp_path / "hoja.csv"


def test_sheet_from_env_uses_google_when_configured(tmp_path: Path) -> None:
    env = {"GOOGLE_SERVICE_ACCOUNT_FILE": str(tmp_path / "sa.json"), "AGENTES_SHEET_ID": "abc"}
    assert isinstance(sheet_from_env(tmp_path, env=env), GoogleSheet)


class FakeWorksheet:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def append_row(self, values: list[str], **kwargs: Any) -> None:
        self.rows.append(values)


class FakeClient:
    def __init__(self) -> None:
        self.worksheet = FakeWorksheet()
        self.opened: list[str] = []

    def open_by_key(self, key: str) -> "FakeClient":
        self.opened.append(key)
        return self

    @property
    def sheet1(self) -> FakeWorksheet:
        return self.worksheet


def test_google_sheet_appends_with_fake_client(tmp_path: Path) -> None:
    client = FakeClient()
    sheet = GoogleSheet("abc", tmp_path / "sa.json", client=client)
    message = sheet.append_row({"cliente": "Ana", "pedido": "42"})
    assert client.opened == ["abc"]
    row = client.worksheet.rows[0]
    assert row[1:] == ["cliente: Ana", "pedido: 42"]
    assert message == "Fila registrada en Google Sheets."

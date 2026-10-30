"""Builds a small fictional knowledge folder (md, txt, pdf, junk) per test."""

from pathlib import Path

import pytest
from pypdf import PdfWriter


def make_pdf(pages: list[str]) -> bytes:
    """Minimal valid PDF with one line of Helvetica text per page (latin-1)."""
    objects: list[bytes] = []
    n = len(pages)
    page_ids = [3 + 2 * i for i in range(n)]
    font_id = 3 + 2 * n
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, text in enumerate(pages):
        content_id = page_ids[i] + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    (folder / "politicas").mkdir(parents=True)
    (folder / "horarios.md").write_text(
        "# Horarios\n\nEl horario de atención es de lunes a sábado de 8 a. m. a 6 p. m.\n",
        encoding="utf-8",
    )
    (folder / "politicas" / "garantias.md").write_text(
        "# Garantías\n\nToda herramienta eléctrica tiene garantía de un año.\n",
        encoding="utf-8",
    )
    (folder / "notas.txt").write_text("Los domicilios cuestan 5.000 pesos.\n", encoding="utf-8")
    (folder / "devoluciones.pdf").write_bytes(
        make_pdf(["Portada del manual", "Devoluciones aceptadas durante 30 dias"])
    )
    blank = PdfWriter()
    blank.add_blank_page(width=612, height=792)
    with (folder / "escaneado.pdf").open("wb") as fh:
        blank.write(fh)
    (folder / "basura.pdf").write_bytes(b"\x00\x01esto no es un pdf")
    (folder / "imagen.png").write_bytes(b"\x89PNG")
    return folder

from pathlib import Path

from agentes.rag import load_chunks


def test_loads_md_txt_pdf_with_sources(docs_dir: Path) -> None:
    chunks, _ = load_chunks(docs_dir)
    sources = {c.source for c in chunks}
    assert sources == {"horarios.md", "politicas/garantias.md", "notas.txt", "devoluciones.pdf"}


def test_pdf_pages_numbered(docs_dir: Path) -> None:
    chunks, _ = load_chunks(docs_dir)
    pdf = sorted((c.page, c.text) for c in chunks if c.source == "devoluciones.pdf")
    assert pdf[0][0] == 1
    assert pdf[1] == (2, "Devoluciones aceptadas durante 30 dias")
    assert all(c.page is None for c in chunks if c.source.endswith(".md"))


def test_junk_and_textless_pdf_skipped_with_warning(docs_dir: Path) -> None:
    _, warnings = load_chunks(docs_dir)
    assert any(w.startswith("Se omitió basura.pdf:") for w in warnings)
    assert any(w.startswith("Se omitió escaneado.pdf:") for w in warnings)
    assert not any("imagen.png" in w for w in warnings)


def test_missing_folder_returns_warning(tmp_path: Path) -> None:
    chunks, warnings = load_chunks(tmp_path / "no-existe")
    assert chunks == []
    assert warnings == [f"La carpeta de documentos no existe: {tmp_path / 'no-existe'}"]


def test_long_document_is_split(tmp_path: Path) -> None:
    (tmp_path / "largo.md").write_text("palabra " * 500, encoding="utf-8")
    chunks, _ = load_chunks(tmp_path, chunk_size=800, overlap=120)
    assert len(chunks) > 1
    assert all(len(c.text) <= 800 for c in chunks)

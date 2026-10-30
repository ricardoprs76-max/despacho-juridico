from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding

from agentes.rag import (
    NO_RESULTS,
    Bm25KnowledgeBase,
    Chunk,
    Hit,
    VectorKnowledgeBase,
    build_knowledge_base,
    format_hits,
    load_chunks,
)


def kb(docs_dir: Path) -> Bm25KnowledgeBase:
    return Bm25KnowledgeBase(load_chunks(docs_dir)[0])


def test_bm25_finds_relevant_chunk(docs_dir: Path) -> None:
    hits = kb(docs_dir).search("horario de atención")
    assert hits[0].chunk.source == "horarios.md"


def test_bm25_accent_insensitive(docs_dir: Path) -> None:
    hits = kb(docs_dir).search("garantia")
    assert hits[0].chunk.source == "politicas/garantias.md"


def test_bm25_no_match_returns_empty(docs_dir: Path) -> None:
    assert kb(docs_dir).search("helicóptero") == []


def test_bm25_empty_corpus_returns_empty() -> None:
    assert Bm25KnowledgeBase([]).search("horario") == []


def test_vector_kb_uses_embeddings(docs_dir: Path) -> None:
    chunks, _ = load_chunks(docs_dir)
    store = VectorKnowledgeBase(chunks, DeterministicFakeEmbedding(size=16))
    assert len(store.search("horario", k=2)) == 2


def test_build_kb_without_key_is_bm25(docs_dir: Path) -> None:
    assert isinstance(build_knowledge_base(load_chunks(docs_dir)[0], env={}), Bm25KnowledgeBase)


def test_format_hits_cites_source_and_page() -> None:
    hits = [
        Hit(Chunk("Abrimos a las 8.", "horarios.md", None), 2.0),
        Hit(Chunk("Devoluciones 30 días.", "manual.pdf", 2), 1.0),
    ]
    text = format_hits(hits)
    assert "[1] Abrimos a las 8.\n(Fuente: horarios.md)" in text
    assert "[2] Devoluciones 30 días.\n(Fuente: manual.pdf, página 2)" in text


def test_format_no_hits_message() -> None:
    assert format_hits([]) == NO_RESULTS
    assert NO_RESULTS == "No encontré información sobre eso en los documentos de la empresa."

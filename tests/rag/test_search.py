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
    kb, warnings = build_knowledge_base(load_chunks(docs_dir)[0], env={})
    assert isinstance(kb, Bm25KnowledgeBase)
    assert warnings == []


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


def test_bm25_single_document_corpus_still_finds_match() -> None:
    kb = Bm25KnowledgeBase([Chunk("El horario es de 8 a 6.", "horarios.md", None)])
    assert [h.chunk.source for h in kb.search("horario")] == ["horarios.md"]


def test_bm25_term_in_every_chunk_still_matches() -> None:
    chunks = [Chunk(f"Sede {n}: horario de 8 a 6.", f"sede{n}.md", None) for n in range(3)]
    assert len(Bm25KnowledgeBase(chunks).search("horario")) == 3


def test_bm25_ignores_spanish_stopwords() -> None:
    chunks = [
        Chunk(
            "Se hacen domicilios de lunes a sábado. El domicilio es gratis.", "domicilios.md", None
        ),
        Chunk("Atendemos en horario de 7 a 6.", "horarios.md", None),
    ]
    hits = Bm25KnowledgeBase(chunks).search("¿Cuál es el horario?")
    assert [h.chunk.source for h in hits] == ["horarios.md"]


class BrokenEmbeddings(DeterministicFakeEmbedding):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("400 API key not valid")


def test_build_kb_falls_back_to_bm25_when_embeddings_fail(docs_dir: Path) -> None:
    chunks = load_chunks(docs_dir)[0]
    kb, warnings = build_knowledge_base(
        chunks, env={"GOOGLE_API_KEY": "mala"}, embeddings=BrokenEmbeddings(size=8)
    )
    assert isinstance(kb, Bm25KnowledgeBase)
    assert warnings == [
        "No se pudieron calcular los embeddings (400 API key not valid); "
        "se usa búsqueda por palabras."
    ]


def test_build_kb_uses_given_embeddings_with_key(docs_dir: Path) -> None:
    chunks = load_chunks(docs_dir)[0]
    kb, warnings = build_knowledge_base(
        chunks, env={"GOOGLE_API_KEY": "k"}, embeddings=DeterministicFakeEmbedding(size=8)
    )
    assert isinstance(kb, VectorKnowledgeBase)
    assert warnings == []


def test_embedding_model_name() -> None:
    from agentes.rag.search import EMBEDDING_MODEL

    assert EMBEDDING_MODEL == "models/gemini-embedding-001"

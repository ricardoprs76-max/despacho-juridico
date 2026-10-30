"""Search a company's document chunks: BM25 offline, or embeddings with a key."""

import os
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from pydantic import SecretStr
from rank_bm25 import BM25Plus

from agentes.rag.loader import Chunk

NO_RESULTS = "No encontré información sobre eso en los documentos de la empresa."
EMBEDDING_MODEL = "models/gemini-embedding-001"
_WORD_RE = re.compile(r"\w+")
# Common Spanish function words (accents already stripped); they match almost every
# chunk and would drown out the words that carry the question's meaning.
# fmt: off
STOPWORDS = frozenset({
    "a", "al", "algo", "como", "con", "cual", "cuales", "cuando", "de", "del", "donde", "el",
    "ella", "en", "es", "esa", "ese", "esta", "este", "hay", "la", "las", "le", "les", "lo",
    "los", "mas", "me", "mi", "no", "o", "para", "pero", "por", "que", "se", "si", "sin", "son",
    "su", "sus", "te", "tu", "un", "una", "uno", "unos", "y", "ya", "yo",
})
# fmt: on


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class KnowledgeBase(Protocol):
    def search(self, query: str, k: int = 4) -> list[Hit]: ...


def _tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(c for c in folded if not unicodedata.combining(c))
    return [word for word in _WORD_RE.findall(without_accents) if word not in STOPWORDS]


class Bm25KnowledgeBase:
    """Keyword search; works offline and needs no API key."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._token_sets = [set(_tokens(c.text)) for c in chunks]
        # BM25+ keeps IDF positive, so tiny corpora (one or two documents) still rank.
        self._index = BM25Plus([_tokens(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, k: int = 4) -> list[Hit]:
        if self._index is None:
            return []
        terms = set(_tokens(query))
        scores = self._index.get_scores(list(terms))
        matching = [
            Hit(chunk, float(score))
            for chunk, tokens, score in zip(self._chunks, self._token_sets, scores, strict=True)
            if tokens & terms
        ]
        return sorted(matching, key=lambda hit: hit.score, reverse=True)[:k]


class VectorKnowledgeBase:
    """Semantic search with an embeddings model, kept in memory."""

    def __init__(self, chunks: list[Chunk], embeddings: Embeddings) -> None:
        self._store = InMemoryVectorStore(embeddings)
        if chunks:
            self._store.add_documents(
                [Document(c.text, metadata={"source": c.source, "page": c.page}) for c in chunks]
            )

    def search(self, query: str, k: int = 4) -> list[Hit]:
        results = self._store.similarity_search_with_score(query, k=k)
        return [
            Hit(Chunk(doc.page_content, doc.metadata["source"], doc.metadata["page"]), score)
            for doc, score in results
        ]


def build_knowledge_base(
    chunks: list[Chunk],
    env: Mapping[str, str] | None = None,
    embeddings: Embeddings | None = None,
) -> tuple[KnowledgeBase, list[str]]:
    """Use embeddings when GOOGLE_API_KEY is set, otherwise (or if they fail) BM25.

    Returns the knowledge base and Spanish warnings for the user.
    """
    env = os.environ if env is None else env
    key = env.get("GOOGLE_API_KEY", "").strip()
    if not key:
        return Bm25KnowledgeBase(chunks), []
    try:
        if embeddings is None:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, api_key=SecretStr(key))
        return VectorKnowledgeBase(chunks, embeddings), []
    except Exception as exc:
        # Invalid key, no network or quota: the agent must still start and answer.
        reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        warning = (
            f"No se pudieron calcular los embeddings ({reason}); se usa búsqueda por palabras."
        )
        return Bm25KnowledgeBase(chunks), [warning]


def format_hits(hits: list[Hit]) -> str:
    """Render hits as numbered passages with their source, for the model to cite."""
    if not hits:
        return NO_RESULTS
    parts = []
    for number, hit in enumerate(hits, 1):
        where = hit.chunk.source
        if hit.chunk.page is not None:
            where += f", página {hit.chunk.page}"
        parts.append(f"[{number}] {hit.chunk.text}\n(Fuente: {where})")
    return "\n\n".join(parts)

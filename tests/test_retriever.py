from collections.abc import Sequence
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from backend.app.chunker import DocumentChunk
from backend.app.retriever import (
    EmbeddingError,
    IndexStorageError,
    LocalVectorRetriever,
)


class FakeEmbedder:
    model_name = "test-embedding-v1"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def is_loaded(self) -> bool:
        return bool(self.calls)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        self.calls.append(list(texts))
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            if "leave" in lowered or "vacation" in lowered:
                vectors.append([1, 0, 0, 0])
            elif "security" in lowered or "password" in lowered:
                vectors.append([0, 1, 0, 0])
            elif "benefit" in lowered:
                vectors.append([0, 0, 1, 0])
            else:
                vectors.append([0, 0, 0, 1])
        return np.asarray(vectors, dtype=np.float32)


class FailingEmbedder(FakeEmbedder):
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise EmbeddingError("model unavailable")


def make_chunk(
    text: str,
    chunk_index: int,
    page_number: int | None = None,
) -> DocumentChunk:
    metadata: dict[str, str | int] = {
        "filename": "policy.pdf",
        "chunk_index": chunk_index,
    }
    if page_number is not None:
        metadata["page_number"] = page_number
    return DocumentChunk(text=text, metadata=metadata)


def test_embeddings_are_generated_and_relevant_chunks_rank_first(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    retriever = LocalVectorRetriever(embedder, tmp_path / "index.sqlite3")
    chunks = [
        make_chunk("Employees receive annual leave each year.", 0, 4),
        make_chunk("Use a unique password to protect account security.", 1, 7),
    ]

    indexed = retriever.index_document("doc-a", "policy.pdf", chunks)
    results = retriever.search("How much vacation leave is offered?", top_k=2)

    assert indexed.status == "indexed"
    assert indexed.chunk_count == 2
    assert embedder.calls[0] == [chunk.text for chunk in chunks]
    assert results[0].text == chunks[0].text
    assert results[0].score == pytest.approx(1.0)


def test_index_persists_and_reloads_with_metadata(tmp_path: Path) -> None:
    index_path = tmp_path / "index.sqlite3"
    first = LocalVectorRetriever(FakeEmbedder(), index_path)
    first.index_document("doc-a", "policy.pdf", [make_chunk("Annual leave policy.", 3, 9)])

    reloaded = LocalVectorRetriever(FakeEmbedder(), index_path)
    results = reloaded.search("vacation leave", top_k=1)

    assert reloaded.index_exists
    assert reloaded.count_chunks() == 1
    assert results[0].document_id == "doc-a"
    assert results[0].filename == "policy.pdf"
    assert results[0].chunk_index == 3
    assert results[0].page_number == 9


def test_multiple_documents_keep_metadata_isolated(tmp_path: Path) -> None:
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "index.sqlite3")
    retriever.index_document("doc-a", "leave.pdf", [make_chunk("Annual leave allowance.", 0, 2)])
    retriever.index_document(
        "doc-b",
        "security.docx",
        [DocumentChunk(text="Account security and password rules.", metadata={"chunk_index": 0})],
    )

    results = retriever.search("vacation leave", top_k=2)

    assert results[0].document_id == "doc-a"
    assert results[0].filename == "leave.pdf"
    assert results[0].page_number == 2
    assert {item.document_id for item in results} == {"doc-a", "doc-b"}
    assert retriever.count_chunks() == 2


def test_empty_index_returns_no_results_without_embedding_query(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    retriever = LocalVectorRetriever(embedder, tmp_path / "index.sqlite3")

    assert retriever.search("anything") == []
    assert embedder.calls == []


def test_empty_query_is_rejected(tmp_path: Path) -> None:
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "index.sqlite3")

    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.search("  ")


def test_failed_embedding_does_not_write_partial_document(tmp_path: Path) -> None:
    retriever = LocalVectorRetriever(FailingEmbedder(), tmp_path / "index.sqlite3")

    with pytest.raises(EmbeddingError):
        retriever.index_document("doc-a", "policy.pdf", [make_chunk("Annual leave.", 0)])

    assert retriever.count_chunks() == 0
    assert not retriever.is_document_indexed("doc-a")


def test_same_document_is_not_embedded_twice(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    retriever = LocalVectorRetriever(embedder, tmp_path / "index.sqlite3")
    chunks = [make_chunk("Annual leave.", 0)]
    retriever.index_document("doc-a", "policy.pdf", chunks)

    result = retriever.index_document("doc-a", "policy.pdf", chunks)

    assert result.status == "already_indexed"
    assert result.chunk_count == 1
    assert len(embedder.calls) == 1


def test_index_rejects_a_different_embedding_model(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite3"
    LocalVectorRetriever(FakeEmbedder(), path).index_document(
        "doc-a", "policy.pdf", [make_chunk("Annual leave.", 0)]
    )
    other = FakeEmbedder()
    other.model_name = "different-model"
    retriever = LocalVectorRetriever(other, path)

    with pytest.raises(IndexStorageError, match="different embedding model"):
        retriever.search("vacation leave")


def test_sqlite_connection_failure_is_reported_as_index_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "index.sqlite3")

    def fail_connect(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("database is unavailable")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)

    with pytest.raises(IndexStorageError, match="could not be opened"):
        retriever.count_chunks()
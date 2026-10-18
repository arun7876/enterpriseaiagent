import json
import logging
import os
import sqlite3
import threading
import uuid
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal, Protocol

import numpy as np
from pydantic import BaseModel, Field

from backend.app.chunker import DocumentChunk
from backend.app.config import settings


logger = logging.getLogger(__name__)
DEFAULT_EMBEDDING_MODEL = settings.embedding_model
DEFAULT_INDEX_PATH = settings.rag_index_path


class RetrieverError(RuntimeError):
    """Base error for embedding or local index failures."""


class EmbeddingError(RetrieverError):
    """Raised when the configured embedding model cannot encode text."""


class IndexStorageError(RetrieverError):
    """Raised when the local vector index cannot be used safely."""


class TextEmbedder(Protocol):
    model_name: str

    @property
    def is_loaded(self) -> bool: ...

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


_MODEL_CACHE: dict[str, Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model: Any | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        with self._lock:
            if self._model is None:
                with _MODEL_CACHE_LOCK:
                    if self.model_name in _MODEL_CACHE:
                        self._model = _MODEL_CACHE[self.model_name]
                    else:
                        try:
                            from sentence_transformers import SentenceTransformer

                            self._model = SentenceTransformer(self.model_name, device="cpu")
                            _MODEL_CACHE[self.model_name] = self._model
                        except Exception as exc:
                            logger.exception("Could not load the configured embedding model.")
                            raise EmbeddingError("The local embedding model could not be loaded.") from exc

            try:
                encoded = self._model.encode(
                    list(texts),
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            except Exception as exc:
                logger.exception("Local embedding generation failed.")
                raise EmbeddingError("Local embedding generation failed.") from exc

        return np.asarray(encoded, dtype=np.float32)


class IndexingResult(BaseModel):
    document_id: str
    status: Literal["indexed", "already_indexed", "empty"]
    chunk_count: int


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    text: str
    chunk_index: int
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float


class LocalVectorRetriever:
    """Persistent exact-cosine vector search backed by transactional SQLite."""

    def __init__(
        self,
        embedder: TextEmbedder | None = None,
        index_path: str | Path | None = None,
    ) -> None:
        self.embedder = embedder or SentenceTransformerEmbedder()
        self.index_path = Path(index_path or DEFAULT_INDEX_PATH)
        self._lock = threading.RLock()
        self._initialize()

    @property
    def index_exists(self) -> bool:
        return self.index_path.is_file()

    @property
    def embedding_model_loaded(self) -> bool:
        return self.embedder.is_loaded

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(str(self.index_path), timeout=30)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            logger.exception("Could not connect to the local vector index.")
            raise IndexStorageError("The local vector index could not be opened.") from exc

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS index_config (
                        config_key TEXT PRIMARY KEY,
                        config_value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS documents (
                        document_id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        indexed_at TEXT NOT NULL,
                        chunk_count INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS chunks (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(document_id)
                            ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        embedding BLOB NOT NULL,
                        embedding_dimensions INTEGER NOT NULL,
                        page_number INTEGER,
                        metadata_json TEXT NOT NULL,
                        UNIQUE(document_id, chunk_index)
                    );
                    CREATE INDEX IF NOT EXISTS chunks_document_id_idx
                        ON chunks(document_id);
                    """
                )
        except (sqlite3.Error, OSError) as exc:
            logger.exception("Could not initialize the persistent vector index.")
            raise IndexStorageError("The local vector index could not be initialized.") from exc

    @staticmethod
    def _normalise_embeddings(encoded: np.ndarray, expected_count: int) -> np.ndarray:
        vectors = np.asarray(encoded, dtype=np.float32)
        if vectors.ndim == 1 and expected_count == 1:
            vectors = vectors.reshape(1, -1)
        if (
            vectors.ndim != 2
            or vectors.shape[0] != expected_count
            or vectors.shape[1] == 0
            or not np.isfinite(vectors).all()
        ):
            raise EmbeddingError("The embedding model returned invalid vectors.")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise EmbeddingError("The embedding model returned an empty vector.")
        return vectors / norms

    def _verify_model(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT config_value FROM index_config WHERE config_key = 'embedding_model'"
        ).fetchone()
        if row is not None and row["config_value"] != self.embedder.model_name:
            raise IndexStorageError("The index was created with a different embedding model.")

    def index_document(
        self,
        document_id: str,
        filename: str,
        chunks: Sequence[DocumentChunk],
    ) -> IndexingResult:
        if not document_id.strip() or not filename.strip():
            raise ValueError("document_id and filename are required.")

        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT chunk_count FROM documents WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return IndexingResult(
                        document_id=document_id,
                        status="already_indexed",
                        chunk_count=int(existing["chunk_count"]),
                    )

                vectors = np.empty((0, 0), dtype=np.float32)
                if chunks:
                    self._verify_model(connection)
                    vectors = self._normalise_embeddings(
                        self.embedder.encode([chunk.text for chunk in chunks]), len(chunks)
                    )

                connection.execute(
                    "INSERT INTO documents(document_id, filename, indexed_at, chunk_count) "
                    "VALUES (?, ?, datetime('now'), ?)",
                    (document_id, filename, len(chunks)),
                )
                if chunks:
                    connection.execute(
                        "INSERT INTO index_config(config_key, config_value) VALUES "
                        "('embedding_model', ?) ON CONFLICT(config_key) DO NOTHING",
                        (self.embedder.model_name,),
                    )
                    connection.executemany(
                        """
                        INSERT INTO chunks(
                            chunk_id, document_id, chunk_index, text, embedding,
                            embedding_dimensions, page_number, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                uuid.uuid4().hex,
                                document_id,
                                int(chunk.metadata.get("chunk_index", chunk_number)),
                                chunk.text,
                                vectors[chunk_number].tobytes(),
                                int(vectors.shape[1]),
                                chunk.metadata.get("page_number"),
                                json.dumps(chunk.metadata, ensure_ascii=True),
                            )
                            for chunk_number, chunk in enumerate(chunks)
                        ],
                    )
                connection.commit()
            except (EmbeddingError, IndexStorageError, ValueError):
                connection.rollback()
                raise
            except sqlite3.Error as exc:
                connection.rollback()
                logger.exception("Could not write document chunks to the vector index.")
                raise IndexStorageError("The local vector index could not be updated.") from exc
            finally:
                connection.close()

        return IndexingResult(
            document_id=document_id,
            status="indexed" if chunks else "empty",
            chunk_count=len(chunks),
        )

    def is_document_indexed(self, document_id: str) -> bool:
        try:
            with self._lock, self._connection() as connection:
                return connection.execute(
                    "SELECT 1 FROM documents WHERE document_id = ?", (document_id,)
                ).fetchone() is not None
        except sqlite3.Error as exc:
            raise IndexStorageError("The local vector index could not be read.") from exc

    def count_chunks(self) -> int:
        try:
            with self._lock, self._connection() as connection:
                row = connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()
                return int(row["count"])
        except sqlite3.Error as exc:
            raise IndexStorageError("The local vector index could not be read.") from exc

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("query must not be empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least one.")
        visible_document_ids = list(document_ids or [])
        if document_ids is not None and not visible_document_ids:
            return []

        with self._lock, self._connection() as connection:
            try:
                query_text = (
                    "SELECT c.chunk_id, c.document_id, c.chunk_index, c.text, c.embedding, "
                    "c.embedding_dimensions, c.page_number, c.metadata_json, d.filename "
                    "FROM chunks c "
                    "JOIN documents d ON d.document_id = c.document_id"
                )
                parameters: tuple[Any, ...] = ()
                if visible_document_ids:
                    placeholders = ", ".join("?" for _ in visible_document_ids)
                    query_text = (
                        query_text + f" WHERE c.document_id IN ({placeholders})"
                    )
                    parameters = tuple(visible_document_ids)
                rows = connection.execute(query_text, parameters).fetchall()
                if not rows:
                    return []

                self._verify_model(connection)
                query_vector = self._normalise_embeddings(self.embedder.encode([query]), 1)[0]
                raw_embeddings = b"".join(bytes(row["embedding"]) for row in rows)
                dims = int(rows[0]["embedding_dimensions"])
                if len(raw_embeddings) != len(rows) * dims * 4:
                    raise IndexStorageError("The vector index contains invalid data.")

                matrix = np.frombuffer(raw_embeddings, dtype=np.float32).reshape(len(rows), dims)
                if matrix.shape[1] != query_vector.size:
                    raise IndexStorageError(
                        "The query embedding dimensions do not match the index."
                    )

                scores = matrix @ query_vector
                order = np.argsort(-scores, kind="stable")[:top_k]
                results: list[RetrievedChunk] = []
                for row_index in order:
                    row = rows[int(row_index)]
                    results.append(
                        RetrievedChunk(
                            chunk_id=row["chunk_id"],
                            document_id=row["document_id"],
                            filename=row["filename"],
                            text=row["text"],
                            chunk_index=int(row["chunk_index"]),
                            page_number=row["page_number"],
                            metadata=json.loads(row["metadata_json"]),
                            score=float(scores[int(row_index)]),
                        )
                    )
                return results
            except (EmbeddingError, IndexStorageError, ValueError):
                raise
            except (sqlite3.Error, json.JSONDecodeError) as exc:
                logger.exception("Could not search the local vector index.")
                raise IndexStorageError("The local vector index could not be searched.") from exc
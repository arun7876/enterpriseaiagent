from collections.abc import Sequence
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.chunker import DocumentChunk
from backend.app.auth import AuthUser, ensure_document_permission
from backend.app.main import app
from backend.app.rag_api import get_default_rag_service
from backend.app.rag_service import LLMUnavailableError, RAGService
from backend.app.retriever import LocalVectorRetriever


class FakeEmbedder:
    model_name = "test-embedding-v1"

    @property
    def is_loaded(self) -> bool:
        return True

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            [[1, 0] if "leave" in text.casefold() or "vacation" in text.casefold() else [0, 1] for text in texts],
            dtype=np.float32,
        )


class FakeLLM:
    model_name = "test-local-model"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def generate(self, prompt: str) -> str:
        if self.fail:
            raise LLMUnavailableError("Ollama is down")
        return "The policy provides annual leave [S1]."

    def model_status(self) -> tuple[bool, bool]:
        return False, False


@pytest.fixture
def rag_client(
    tmp_path: Path,
    auth_headers: dict[str, str],
    auth_user: AuthUser,
) -> tuple[TestClient, RAGService]:
    ensure_document_permission("doc-policy", auth_user.id)
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "index.sqlite3")
    retriever.index_document(
        "doc-policy",
        "employee-policy.pdf",
        [
            DocumentChunk(
                text="Employees receive annual leave each year.",
                metadata={"chunk_index": 0, "page_number": 4},
            )
        ],
    )
    service = RAGService(retriever, FakeLLM(), min_relevance_score=0.3)
    app.dependency_overrides[get_default_rag_service] = lambda: service
    with TestClient(app, headers=auth_headers) as client:
        yield client, service
    app.dependency_overrides.clear()


def test_ask_endpoint_returns_citations_from_index(rag_client: tuple[TestClient, RAGService]) -> None:
    client, _ = rag_client

    response = client.post(
        "/api/v1/chat/ask",
        json={"question": "What is the annual vacation leave policy?", "top_k": 5},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "The policy provides annual leave [S1]."
    assert result["source_filenames"] == ["employee-policy.pdf"]
    assert result["retrieval_count"] == 1
    assert result["citations"][0]["page_number"] == 4
    assert result["citations"][0]["document_id"] == "doc-policy"


def test_rag_status_reports_index_and_model_state(
    rag_client: tuple[TestClient, RAGService],
) -> None:
    client, _ = rag_client

    response = client.get("/api/v1/rag/status")

    assert response.status_code == 200
    assert response.json() == {
        "embedding_model_identifier": "test-embedding-v1",
        "embedding_model_loaded": True,
        "vector_index_exists": True,
        "indexed_chunk_count": 1,
        "model_identifier": "test-local-model",
        "llm_reachable": False,
        "llm_model_available": False,
    }


def test_ask_endpoint_rejects_blank_questions(rag_client: tuple[TestClient, RAGService]) -> None:
    client, _ = rag_client

    response = client.post("/api/v1/chat/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_endpoint_maps_ollama_errors_to_service_unavailable(
    tmp_path: Path,
    auth_headers: dict[str, str],
    auth_user: AuthUser,
) -> None:
    ensure_document_permission("doc-policy", auth_user.id)
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "index.sqlite3")
    retriever.index_document(
        "doc-policy",
        "employee-policy.pdf",
        [DocumentChunk(text="Annual leave policy.", metadata={"chunk_index": 0})],
    )
    service = RAGService(retriever, FakeLLM(fail=True), min_relevance_score=0.3)
    app.dependency_overrides[get_default_rag_service] = lambda: service
    try:
        with TestClient(app, headers=auth_headers) as client:
            response = client.post(
                "/api/v1/chat/ask",
                json={"question": "What is the vacation leave policy?"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "The configured local Ollama model is unavailable or timed out."


def test_existing_health_routes_remain_available(rag_client: tuple[TestClient, RAGService]) -> None:
    client, _ = rag_client

    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/docs").status_code == 200
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import agent_api
from backend.app.auth import AuthUser, ensure_document_permission
from backend.app.agent_api import get_agent
from backend.app.agent_graph import AgentWorkflowError, EnterpriseAgent
from backend.app.main import app
from backend.app.rag_service import Citation, LLMUnavailableError, RAGAnswer
from backend.app.sql_tools import BusinessSQLTools, SQLToolUnavailableError


class FakeLLM:
    model_name = "test-agent-model"

    def generate(self, prompt: str) -> str:
        return "Department sales are summarized with the policy context [S1]. [S99]"


class FakeRAGService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.llm_client = FakeLLM()

    def ask(self, question: str, document_ids: list[str] | None = None) -> RAGAnswer:
        if document_ids is not None and "policy-doc" not in document_ids:
            return RAGAnswer(
                answer="No permitted evidence was found.",
                citations=[],
                source_filenames=[],
                retrieval_count=0,
                model_identifier="test-agent-model",
                processing_time_ms=1,
            )
        if self.fail:
            raise LLMUnavailableError("mock unavailable")
        citation = Citation(
            source_id="S1",
            document_id="policy-doc",
            chunk_id="policy-chunk",
            filename="annual-policy.pdf",
            chunk_index=1,
            page_number=5,
            excerpt="Employees receive annual paid leave.",
            relevance_score=0.8,
            metadata={"page_number": 5},
        )
        return RAGAnswer(
            answer="Employees receive annual paid leave [S1].",
            citations=[citation],
            source_filenames=["annual-policy.pdf"],
            retrieval_count=1,
            model_identifier="test-agent-model",
            processing_time_ms=1,
        )


@pytest.fixture
def agent_client(
    tmp_path: Path,
    auth_headers: dict[str, str],
    auth_user: AuthUser,
) -> TestClient:
    ensure_document_permission("policy-doc", auth_user.id)
    agent = EnterpriseAgent(
        FakeRAGService(),
        BusinessSQLTools(tmp_path / "business.sqlite3"),
    )
    app.dependency_overrides[get_agent] = lambda: agent
    try:
        with TestClient(app, headers=auth_headers) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_agent_endpoint_answers_document_question(agent_client: TestClient) -> None:
    response = agent_client.post(
        "/api/v1/agent/ask",
        json={"question": "What is the annual leave policy?", "include_sources": True},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["workflow"] == "document_search"
    assert result["sufficient_evidence"] is True
    assert result["citations"][0]["filename"] == "annual-policy.pdf"
    assert result["citations"][0]["page_number"] == 5
    assert result["structured_data"] == []


def test_agent_endpoint_answers_sql_question(agent_client: TestClient) -> None:
    response = agent_client.post(
        "/api/v1/agent/ask",
        json={
            "question": "What were sales from 2026-09-01 to 2026-09-30?",
            "include_sources": False,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["workflow"] == "sql_analytics"
    assert "5,050.00" in result["answer"]
    assert result["structured_data"][0]["tool_name"] == "total_sales"
    assert result["citations"] == []


def test_agent_endpoint_combines_sql_results_and_document_citations(
    agent_client: TestClient,
) -> None:
    response = agent_client.post(
        "/api/v1/agent/ask",
        json={
            "question": (
                "Compare sales across departments and explain using the uploaded sales report "
                "from 2026-09-01 to 2026-09-30."
            )
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["workflow"] == "combined"
    assert result["sufficient_evidence"] is True
    assert len(result["structured_data"][0]["rows"]) == 3
    assert result["citations"][0]["page_number"] == 5
    assert "[S99]" not in result["answer"]


def test_agent_endpoint_rejects_blank_question(agent_client: TestClient) -> None:
    response = agent_client.post("/api/v1/agent/ask", json={"question": "  "})

    assert response.status_code == 422


def test_agent_endpoint_sanitizes_workflow_failure(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    class FailingAgent:
        def ask(
            self,
            question: str,
            include_sources: bool = True,
            allowed_document_ids: list[str] | None = None,
        ) -> None:
            raise AgentWorkflowError("internal path and traceback must not leak")

    app.dependency_overrides[get_agent] = lambda: FailingAgent()
    try:
        with TestClient(app, headers=auth_headers) as client:
            response = client.post(
                "/api/v1/agent/ask",
                json={"question": "What is the annual leave policy?"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "The agent workflow could not be completed."}


def test_agent_endpoint_sanitizes_default_data_service_failure(
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    def fail_to_initialize() -> None:
        raise SQLToolUnavailableError("private database location")

    monkeypatch.setattr(agent_api, "get_default_agent", fail_to_initialize)

    with TestClient(app, headers=auth_headers) as client:
        response = client.post(
            "/api/v1/agent/ask",
            json={"question": "What were total sales last month?"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "The agent data services are unavailable."}
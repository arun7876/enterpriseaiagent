from collections.abc import Iterator, Sequence
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import agent_api, documents as documents_api
from backend.app.agent_graph import EnterpriseAgent
from backend.app.auth import AuthUser, get_visible_document_ids_for_user, user_can_access_document
from backend.app.main import app
from backend.app.rag_api import get_default_rag_service
from backend.app.rag_service import RAGService
from backend.app.retriever import LocalVectorRetriever
from backend.app.sql_tools import BusinessSQLTools


class FakeEmbedder:
    model_name = "security-test-embedding"

    @property
    def is_loaded(self) -> bool:
        return True

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)


class FakeLLM:
    model_name = "security-test-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "The permitted evidence does not contain enough information."

    def model_status(self) -> tuple[bool, bool]:
        return False, False


@pytest.fixture(autouse=True)
def isolated_security_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[RAGService]:
    retriever = LocalVectorRetriever(FakeEmbedder(), tmp_path / "security-index.sqlite3")
    fake_llm = FakeLLM()
    service = RAGService(retriever, fake_llm, min_relevance_score=0.3)
    monkeypatch.setattr(documents_api, "get_default_rag_service", lambda: service)
    app.dependency_overrides[get_default_rag_service] = lambda: service
    agent = EnterpriseAgent(service, BusinessSQLTools(tmp_path / "security-business.sqlite3"))
    app.dependency_overrides[agent_api.get_agent] = lambda: agent
    yield service
    app.dependency_overrides.clear()


client = TestClient(app)


def test_security_isolation_script_uses_temporary_auth_database(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "check_security_isolation.py"
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    reported_paths = {
        key: Path(value).resolve()
        for line in completed.stdout.splitlines()
        if "=" in line
        for key, value in [line.split("=", maxsplit=1)]
        if key in {"isolated_data_dir", "auth_database", "document_catalog"}
    }
    isolated_data_dir = reported_paths["isolated_data_dir"]
    assert reported_paths["auth_database"] == isolated_data_dir / "auth.sqlite3"
    assert reported_paths["document_catalog"] == isolated_data_dir / "documents.sqlite3"
    assert reported_paths["auth_database"] != (project_root / "data" / "auth.sqlite3").resolve()
    assert not isolated_data_dir.exists()
    assert "security_isolation=passed" in completed.stdout


def test_registration_and_login_return_user_and_token() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "StrongPass123", "role": "analyst"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "alice@example.com"
    assert payload["user"]["role"] == "analyst"
    assert payload["token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_public_registration_cannot_assign_admin_role() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "self-admin@example.com", "password": "StrongPass123", "role": "admin"},
    )

    assert response.status_code == 422


def test_document_permission_helpers_fail_closed(auth_user: AuthUser) -> None:
    assert get_visible_document_ids_for_user(None) == []
    assert user_can_access_document(None, "unknown-document") is False
    assert get_visible_document_ids_for_user(auth_user) == []
    assert user_can_access_document(auth_user, "unknown-document") is False


def test_cookie_authenticated_mutations_require_csrf_header() -> None:
    with TestClient(app) as cookie_client:
        registered = cookie_client.post(
            "/api/v1/auth/register",
            json={"email": "csrf-check@example.com", "password": "StrongPass123", "role": "analyst"},
        )
        assert registered.status_code == 200
        assert "csrf_token" in cookie_client.cookies

        response = cookie_client.post(
            "/api/v1/chat/ask",
            json={"question": "Search my documents"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed."


def test_document_access_is_scoped_by_owner() -> None:
    alice = client.post(
        "/api/v1/auth/register",
        json={"email": "alice-access@example.com", "password": "StrongPass123", "role": "analyst"},
    )
    bob = client.post(
        "/api/v1/auth/register",
        json={"email": "bob-access@example.com", "password": "StrongPass123", "role": "viewer"},
    )

    token_a = alice.json()["token"]
    token_b = bob.json()["token"]

    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": ("private.csv", b"department\nSales\n", "text/csv")},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert uploaded.status_code == 200
    document_id = uploaded.json()["document_id"]

    alice_list = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    bob_list = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert alice_list.status_code == 200
    assert any(item["document_id"] == document_id for item in alice_list.json())
    assert bob_list.status_code == 200
    assert all(item["document_id"] != document_id for item in bob_list.json())

    restricted = client.post(
        "/api/v1/chat/ask",
        json={"question": "What does the document say?", "top_k": 3},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert restricted.status_code == 200
    assert restricted.json()["retrieval_count"] == 0


def test_rag_ignores_private_document_chunks_for_unauthorized_user(
    isolated_security_services: RAGService,
) -> None:
    alice = client.post(
        "/api/v1/auth/register",
        json={"email": "alice-rag@example.com", "password": "StrongPass123", "role": "analyst"},
    )
    bob = client.post(
        "/api/v1/auth/register",
        json={"email": "bob-rag@example.com", "password": "StrongPass123", "role": "viewer"},
    )

    alice_token = alice.json()["token"]
    bob_token = bob.json()["token"]

    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": ("private-rag.csv", b"department, revenue\nQ4, 8.2M\n", "text/csv")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert uploaded.status_code == 200
    private_payload = uploaded.json()
    assert private_payload["document_id"]

    response = client.post(
        "/api/v1/chat/ask",
        json={"question": "Summarize the hidden Q4 revenue document.", "top_k": 5},
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["retrieval_count"] == 0
    assert content["citations"] == []
    text = str(content.get("answer", "")).lower()
    assert "8.2m" not in text
    assert "q4 revenue" not in text
    assert isolated_security_services.llm_client.prompts == []


def test_agent_cannot_bypass_document_permissions(
    isolated_security_services: RAGService,
) -> None:
    alice = client.post(
        "/api/v1/auth/register",
        json={"email": "alice-agent@example.com", "password": "StrongPass123", "role": "analyst"},
    )
    bob = client.post(
        "/api/v1/auth/register",
        json={"email": "bob-agent@example.com", "password": "StrongPass123", "role": "viewer"},
    )

    alice_token = alice.json()["token"]
    bob_token = bob.json()["token"]

    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": ("private-agent.csv", b"team, capacity\nNorth, 42%\n", "text/csv")},
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert uploaded.status_code == 200

    response = client.post(
        "/api/v1/agent/ask",
        json={"question": "What is the team capacity in the private memo?", "include_sources": True},
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"] == []
    assert payload["sufficient_evidence"] is False
    lowered = str(payload.get("answer", "")).lower()
    assert "42 percent" not in lowered
    assert "team capacity" not in lowered
    assert isolated_security_services.llm_client.prompts == []

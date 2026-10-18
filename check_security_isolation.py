import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


class FakeEmbedder:
    model_name = "security-test-embedding"

    @property
    def is_loaded(self) -> bool:
        return True

    def encode(self, texts: Sequence[str]):
        import numpy as np

        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)


class FakeLLM:
    model_name = "security-test-model"

    def generate(self, prompt: str) -> str:
        return "The permitted evidence does not contain enough information."

    def model_status(self) -> tuple[bool, bool]:
        return False, False


def run_isolated() -> None:
    data_dir = Path(os.environ["DATA_DIR"])
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root))

    from fastapi.testclient import TestClient

    from backend.app import agent_api, auth as auth_mod, documents as documents_api
    from backend.app.agent_graph import EnterpriseAgent
    from backend.app.main import app
    from backend.app.rag_api import get_default_rag_service
    from backend.app.rag_service import RAGService
    from backend.app.retriever import LocalVectorRetriever
    from backend.app.sql_tools import BusinessSQLTools

    expected_auth_db = data_dir / "auth.sqlite3"
    expected_catalog_db = data_dir / "documents.sqlite3"
    if auth_mod.AUTH_DB_PATH.resolve() != expected_auth_db.resolve():
        raise RuntimeError(
            f"Auth DB escaped the isolated data directory: {auth_mod.AUTH_DB_PATH}"
        )
    if documents_api.DOCUMENT_CATALOG_PATH.resolve() != expected_catalog_db.resolve():
        raise RuntimeError(
            "Document catalog escaped the isolated data directory: "
            f"{documents_api.DOCUMENT_CATALOG_PATH}"
        )

    service = RAGService(
        LocalVectorRetriever(FakeEmbedder(), data_dir / "index" / "vector_index.sqlite3"),
        FakeLLM(),
        min_relevance_score=0.3,
    )
    documents_api.get_default_rag_service = lambda: service
    app.dependency_overrides[get_default_rag_service] = lambda: service
    agent = EnterpriseAgent(
        service,
        BusinessSQLTools(data_dir / "business_analytics.sqlite3"),
    )
    app.dependency_overrides[agent_api.get_agent] = lambda: agent

    print(f"isolated_data_dir={data_dir}")
    print(f"auth_database={auth_mod.AUTH_DB_PATH}")
    print(f"document_catalog={documents_api.DOCUMENT_CATALOG_PATH}")

    try:
        with TestClient(app) as client:
            alice = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "alice-security@example.com",
                    "password": "StrongPass123",
                    "role": "analyst",
                },
            )
            bob = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "bob-security@example.com",
                    "password": "StrongPass123",
                    "role": "viewer",
                },
            )
            assert alice.status_code == 200, alice.text
            assert bob.status_code == 200, bob.text
            alice_token = alice.json()["token"]
            bob_token = bob.json()["token"]

            uploaded = client.post(
                "/api/v1/documents/upload",
                files={
                    "file": (
                        "private.csv",
                        b"department\nSales\n",
                        "text/csv",
                    )
                },
                headers={"Authorization": f"Bearer {alice_token}"},
            )
            assert uploaded.status_code == 200, uploaded.text
            private_document_id = uploaded.json()["document_id"]
            print(f"private_document_id={private_document_id}")

            bob_chat = client.post(
                "/api/v1/chat/ask",
                json={"question": "What does the document say?", "top_k": 3},
                headers={"Authorization": f"Bearer {bob_token}"},
            )
            assert bob_chat.status_code == 200, bob_chat.text
            assert bob_chat.json()["retrieval_count"] == 0

            bob_agent = client.post(
                "/api/v1/agent/ask",
                json={
                    "question": "What does the document say?",
                    "include_sources": True,
                },
                headers={"Authorization": f"Bearer {bob_token}"},
            )
            assert bob_agent.status_code == 200, bob_agent.text
            assert bob_agent.json()["citations"] == []
            assert bob_agent.json()["sufficient_evidence"] is False
    finally:
        app.dependency_overrides.clear()

    print("security_isolation=passed")


def main() -> None:
    if sys.argv[1:] == ["--run-isolated"]:
        run_isolated()
        return

    project_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="enterprise-ai-security-") as temporary_dir:
        data_dir = Path(temporary_dir)
        for directory in ("uploads", "index", "models", "huggingface"):
            (data_dir / directory).mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment.update(
            {
                "APP_ENV": "test",
                "DATA_DIR": str(data_dir),
                "AUTH_DB_PATH": str(data_dir / "auth.sqlite3"),
                "DOCUMENT_CATALOG_PATH": str(data_dir / "documents.sqlite3"),
                "UPLOAD_DIR": str(data_dir / "uploads"),
                "RAG_INDEX_PATH": str(data_dir / "index" / "vector_index.sqlite3"),
                "BUSINESS_DB_PATH": str(data_dir / "business_analytics.sqlite3"),
                "HF_HOME": str(data_dir / "models" / "huggingface"),
            }
        )
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--run-isolated"],
            cwd=project_root,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

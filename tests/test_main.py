import sqlite3
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_module
from backend.app.main import app


client = TestClient(app)


def test_root_returns_project_information() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Enterprise AI Research Agent",
        "version": "0.1.0",
        "description": "A locally runnable foundation for enterprise document research.",
    }


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_private_data_routes_require_authentication() -> None:
    with TestClient(app) as unauthenticated_client:
        assert unauthenticated_client.get("/api/v1/documents").status_code == 401
        assert unauthenticated_client.post(
            "/api/v1/chat/ask",
            json={"question": "Search private documents"},
        ).status_code == 401
        assert unauthenticated_client.post(
            "/api/v1/agent/ask",
            json={"question": "Search private documents"},
        ).status_code == 401


def test_request_id_is_returned_to_the_caller() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "phase7-check-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase7-check-1"


def test_readiness_reports_cold_embeddings_and_unreachable_model_as_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vector_path = tmp_path / "vector.sqlite3"
    auth_path = tmp_path / "auth.sqlite3"
    business_path = tmp_path / "business.sqlite3"
    catalog_path = tmp_path / "documents.sqlite3"
    for path in (vector_path, auth_path, business_path, catalog_path):
        with sqlite3.connect(path) as connection:
            connection.execute("SELECT 1")

    service = SimpleNamespace(
        retriever=SimpleNamespace(index_path=vector_path, embedding_model_loaded=False),
        llm_client=SimpleNamespace(model_status=lambda: (False, False)),
    )
    monkeypatch.setattr(main_module, "get_default_rag_service", lambda: service)
    monkeypatch.setattr(main_module, "get_default_sql_tools", lambda: None)
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(
            main_module.settings,
            auth_db_path=auth_path,
            document_catalog_path=catalog_path,
            business_db_path=business_path,
            upload_dir=tmp_path / "uploads",
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {
            "ollama": "unreachable",
            "embedding_model": "not_loaded",
            "vector_index": "available",
            "auth_database": "available",
            "document_catalog": "available",
            "business_database": "available",
            "upload_storage": "writable",
        },
    }


def test_readiness_reports_ready_when_all_dependencies_are_healthy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vector_path = tmp_path / "vector.sqlite3"
    auth_path = tmp_path / "auth.sqlite3"
    business_path = tmp_path / "business.sqlite3"
    catalog_path = tmp_path / "documents.sqlite3"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for path in (vector_path, auth_path, business_path, catalog_path):
        with sqlite3.connect(path) as connection:
            connection.execute("SELECT 1")

    service = SimpleNamespace(
        retriever=SimpleNamespace(index_path=vector_path, embedding_model_loaded=True),
        llm_client=SimpleNamespace(model_status=lambda: (True, True)),
    )
    monkeypatch.setattr(main_module, "get_default_rag_service", lambda: service)
    monkeypatch.setattr(main_module, "get_default_sql_tools", lambda: None)
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(
            main_module.settings,
            auth_db_path=auth_path,
            document_catalog_path=catalog_path,
            business_db_path=business_path,
            upload_dir=upload_dir,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "ollama": "model_available",
            "embedding_model": "loaded",
            "vector_index": "available",
            "auth_database": "available",
            "document_catalog": "available",
            "business_database": "available",
            "upload_storage": "writable",
        },
    }


def test_request_id_generated_when_omitted_or_malformed() -> None:
    with TestClient(app) as client:
        response_missing = client.get("/api/v1/health")
        generated_id = response_missing.headers.get("X-Request-ID")
        assert generated_id is not None
        assert len(generated_id) == 32

        response_malformed = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "bad id with spaces & symbols <script>"},
        )
        sanitized_id = response_malformed.headers.get("X-Request-ID")
        assert sanitized_id is not None
        assert sanitized_id != "bad id with spaces & symbols <script>"
        assert len(sanitized_id) == 32


def test_json_log_formatter_structure() -> None:
    import json
    import logging
    from backend.app.observability import JsonLogFormatter

    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345"
    record.method = "GET"
    record.path = "/api/v1/health"
    record.status_code = 200
    record.duration_ms = 4.2

    output = formatter.format(record)
    data = json.loads(output)
    assert data["logger"] == "test.logger"
    assert data["severity"] == "INFO"
    assert data["message"] == "test message"
    assert data["request_id"] == "req-12345"
    assert data["method"] == "GET"
    assert data["path"] == "/api/v1/health"
    assert data["status_code"] == 200
    assert data["duration_ms"] == 4.2
    assert "timestamp" in data


def test_swagger_docs_are_available() -> None:
    response = client.get("/docs")

    assert response.status_code == 200

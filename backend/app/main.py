import logging
import os
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.auth import router as auth_router
from backend.app.agent_api import router as agent_router
from backend.app.documents import router as documents_router
from backend.app.observability import RequestLoggingMiddleware, configure_logging
from backend.app.rag_api import router as rag_router
from backend.app.rag_service import OllamaClient, get_default_rag_service
from backend.app.retriever import RetrieverError
from backend.app.sql_tools import SQLToolUnavailableError, get_default_sql_tools


configure_logging()
logger = logging.getLogger(__name__)


class ProjectInfo(BaseModel):
    name: str
    version: str
    description: str


class HealthStatus(BaseModel):
    status: Literal["ok"]


class ReadinessStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, str]


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    logger.info("application startup", extra={"event": "startup"})
    if not os.getenv("PYTEST_CURRENT_TEST") and os.getenv("WARMUP_EMBEDDING_ON_STARTUP", "true").lower() in ("1", "true", "yes"):
        import threading

        def _warmup() -> None:
            try:
                logger.info("Starting background embedding model warmup...")
                service = get_default_rag_service()
                service.retriever.embedder.encode(["warmup probe"])
                logger.info("Background embedding model warmup complete.")
            except Exception as exc:
                logger.warning("Background embedding warmup did not complete: %s", exc)

        threading.Thread(target=_warmup, daemon=True, name="embedding-warmup").start()

    try:
        yield
    finally:
        logger.info("application shutdown", extra={"event": "shutdown"})


app = FastAPI(
    title="Enterprise AI Research Agent",
    version="0.1.0",
    description="A locally runnable foundation for enterprise document research.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(agent_router)
app.include_router(auth_router)


@app.get("/", response_model=ProjectInfo, tags=["project"])
def read_root() -> ProjectInfo:
    return ProjectInfo(
        name="Enterprise AI Research Agent",
        version=app.version,
        description="A locally runnable foundation for enterprise document research.",
    )


@app.get("/api/v1/health", response_model=HealthStatus, tags=["operations"])
def read_health() -> HealthStatus:
    return HealthStatus(status="ok")


def _sqlite_probe(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=1)
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
        return True
    except (OSError, sqlite3.Error):
        return False


def _upload_storage_writable(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.is_dir() or not os.access(candidate, os.W_OK):
        return False
    try:
        with tempfile.TemporaryFile(dir=candidate):
            pass
        return True
    except OSError:
        return False


@app.get("/api/v1/ready", response_model=ReadinessStatus, tags=["operations"])
def read_readiness(response: Response) -> ReadinessStatus:
    try:
        service = get_default_rag_service()
        vector_index_ready = _sqlite_probe(service.retriever.index_path)
        embedding_model_loaded = service.retriever.embedding_model_loaded
        ollama_client = service.llm_client
    except RetrieverError:
        vector_index_ready = False
        embedding_model_loaded = False
        ollama_client = OllamaClient()
    ollama_reachable, model_available = ollama_client.model_status()
    try:
        get_default_sql_tools()
        business_database_ready = _sqlite_probe(settings.business_db_path)
    except SQLToolUnavailableError:
        business_database_ready = False
    dependencies = {
        "ollama": "model_available" if model_available else "model_missing" if ollama_reachable else "unreachable",
        "embedding_model": "loaded" if embedding_model_loaded else "not_loaded",
        "vector_index": "available" if vector_index_ready else "unavailable",
        "auth_database": "available" if _sqlite_probe(settings.auth_db_path) else "unavailable",
        "document_catalog": "available" if _sqlite_probe(settings.document_catalog_path) else "unavailable",
        "business_database": "available" if business_database_ready else "unavailable",
        "upload_storage": "writable" if _upload_storage_writable(settings.upload_dir) else "unavailable",
    }
    storage_ready = all(
        dependencies[name] in {"available", "writable"}
        for name in (
            "vector_index",
            "auth_database",
            "document_catalog",
            "business_database",
            "upload_storage",
        )
    )
    is_ready = (
        storage_ready
        and dependencies["ollama"] == "model_available"
        and dependencies["embedding_model"] == "loaded"
    )
    if not is_ready:
        response.status_code = 503
    return ReadinessStatus(status="ready" if is_ready else "not_ready", dependencies=dependencies)

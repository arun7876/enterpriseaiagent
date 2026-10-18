import logging
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.auth import AuthUser, get_visible_document_ids_for_user, require_auth
from backend.app.chunker import chunk_document
from backend.app.config import settings
from backend.app.document_processor import (
    DocumentProcessingError,
    ProcessedDocument,
    UnsupportedDocumentTypeError,
    process_document,
)
from backend.app.rag_service import get_default_rag_service
from backend.app.retriever import RetrieverError


logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size_bytes

UPLOAD_DIR = settings.upload_dir
DOCUMENT_CATALOG_PATH = settings.document_catalog_path
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".csv"}
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class DocumentSummary(BaseModel):
    document_id: str
    original_filename: str
    file_type: str
    extraction_status: str
    uploaded_at: datetime
    chunk_count: int
    indexing_status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentUploadResponse(ProcessedDocument):
    document_id: str
    uploaded_at: datetime
    chunk_count: int
    indexing_status: Literal["indexed", "already_indexed", "empty", "failed"]
    indexing_error: str | None = None



def _initialize_document_catalog() -> None:
    DOCUMENT_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DOCUMENT_CATALOG_PATH), timeout=10) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS documents ("
            "document_id TEXT PRIMARY KEY, summary_json TEXT NOT NULL)"
        )


def _save_document_summary(summary: DocumentSummary) -> None:
    with sqlite3.connect(str(DOCUMENT_CATALOG_PATH), timeout=10) as connection:
        connection.execute(
            "INSERT INTO documents(document_id, summary_json) VALUES (?, ?) "
            "ON CONFLICT(document_id) DO UPDATE SET summary_json = excluded.summary_json",
            (summary.document_id, summary.model_dump_json()),
        )


def _read_document_summaries() -> list[DocumentSummary]:
    with sqlite3.connect(str(DOCUMENT_CATALOG_PATH), timeout=10) as connection:
        rows = connection.execute(
            "SELECT summary_json FROM documents ORDER BY rowid DESC"
        ).fetchall()
    return [DocumentSummary.model_validate_json(row[0]) for row in rows]


_initialize_document_catalog()


def _safe_original_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    safe_name = "".join(character for character in normalized if character.isprintable())
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )
    return safe_name[:255]


def _remove_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not clean up a failed document upload.")


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile = File(...),
    user: AuthUser = Depends(require_auth),
) -> DocumentUploadResponse:
    stored_path: Path | None = None
    try:
        if user.role == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewers cannot upload or edit documents.",
            )
        original_filename = _safe_original_filename(file.filename)
        extension = Path(original_filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Supported file types are PDF, DOCX, and CSV.",
            )
        if file.size is not None and file.size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="The uploaded file exceeds the maximum allowed size.",
            )

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"
        total_size = 0
        file.file.seek(0)
        with stored_path.open("xb") as destination:
            while chunk := file.file.read(64 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="The uploaded file exceeds the maximum allowed size.",
                    )
                destination.write(chunk)

        processed = process_document(stored_path, original_filename)
        document_id = uuid.uuid4().hex
        uploaded_at = datetime.now(timezone.utc)
        chunks = chunk_document(processed)
        indexing_error: str | None = None
        try:
            indexing_result = get_default_rag_service().retriever.index_document(
                document_id,
                processed.original_filename,
                chunks,
            )
            indexing_status = indexing_result.status
        except RetrieverError:
            logger.exception("Document was extracted but could not be indexed.")
            indexing_status = "failed"
            indexing_error = (
                "Local indexing failed; the document was stored but is not searchable."
            )

        response = DocumentUploadResponse(
            **processed.model_dump(),
            document_id=document_id,
            uploaded_at=uploaded_at,
            chunk_count=len(chunks),
            indexing_status=indexing_status,
            indexing_error=indexing_error,
        )
        summary = DocumentSummary(
            document_id=document_id,
            original_filename=processed.original_filename,
            file_type=processed.file_type,
            extraction_status=processed.extraction_status,
            uploaded_at=uploaded_at,
            chunk_count=len(chunks),
            indexing_status=indexing_status,
            metadata=processed.metadata,
        )
        from backend.app.auth import ensure_document_permission

        ensure_document_permission(document_id, user.id, "private")
        _save_document_summary(summary)
        return response
    except HTTPException:
        _remove_file(stored_path)
        raise
    except UnsupportedDocumentTypeError as exc:
        _remove_file(stored_path)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported file types are PDF, DOCX, and CSV.",
        ) from exc
    except DocumentProcessingError as exc:
        _remove_file(stored_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded document is invalid or could not be extracted.",
        ) from exc
    except OSError as exc:
        _remove_file(stored_path)
        logger.exception("Document upload storage failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The uploaded document could not be stored.",
        ) from exc
    except Exception as exc:
        _remove_file(stored_path)
        logger.exception("Unexpected document upload processing failure.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The uploaded document could not be processed.",
        ) from exc
    finally:
        try:
            file.file.close()
        except OSError:
            logger.warning("Could not close the uploaded document stream.")


@router.get("", response_model=list[DocumentSummary])
def list_documents(user: AuthUser = Depends(require_auth)) -> list[DocumentSummary]:
    documents = _read_document_summaries()
    if user.role == "admin":
        return documents
    allowed_ids = set(get_visible_document_ids_for_user(user) or [])
    return [document for document in documents if document.document_id in allowed_ids]
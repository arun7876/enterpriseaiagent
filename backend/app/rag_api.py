from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.app.auth import AuthUser, get_visible_document_ids_for_user, require_auth
from backend.app.rag_service import (
    LLMUnavailableError,
    RAGAnswer,
    RAGService,
    get_default_rag_service,
)
from backend.app.retriever import EmbeddingError, IndexStorageError, RetrieverError


router = APIRouter(prefix="/api/v1", tags=["rag"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank.")
        return question


class RAGStatusResponse(BaseModel):
    embedding_model_identifier: str
    embedding_model_loaded: bool
    vector_index_exists: bool
    indexed_chunk_count: int
    model_identifier: str
    llm_reachable: bool
    llm_model_available: bool


@router.post("/chat/ask", response_model=RAGAnswer)
def ask_question(
    request: AskRequest,
    user: AuthUser = Depends(require_auth),
    service: RAGService = Depends(get_default_rag_service),
) -> RAGAnswer:
    allowed_document_ids = get_visible_document_ids_for_user(user)
    try:
        return service.ask(
            request.question,
            top_k=request.top_k,
            document_ids=allowed_document_ids,
        )
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local embedding model is unavailable. Check its installation and model cache.",
        ) from exc
    except IndexStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local document index is unavailable.",
        ) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The configured local Ollama model is unavailable or timed out.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question or retrieval options are invalid.",
        ) from exc


@router.get("/rag/status", response_model=RAGStatusResponse)
def read_rag_status(
    service: RAGService = Depends(get_default_rag_service),
) -> RAGStatusResponse:
    try:
        indexed_chunk_count = service.retriever.count_chunks()
    except RetrieverError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local document index is unavailable.",
        ) from exc

    llm_reachable, llm_model_available = service.llm_client.model_status()
    return RAGStatusResponse(
        embedding_model_identifier=service.retriever.embedder.model_name,
        embedding_model_loaded=service.retriever.embedding_model_loaded,
        vector_index_exists=service.retriever.index_exists,
        indexed_chunk_count=indexed_chunk_count,
        model_identifier=service.llm_client.model_name,
        llm_reachable=llm_reachable,
        llm_model_available=llm_model_available,
    )
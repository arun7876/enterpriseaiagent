import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from backend.app.auth import AuthUser, get_visible_document_ids_for_user, require_auth
from backend.app.agent_graph import AgentResponse, AgentWorkflowError, EnterpriseAgent
from backend.app.rag_service import get_default_rag_service
from backend.app.sql_tools import (
    BusinessSQLTools,
    SQLToolUnavailableError,
    get_default_sql_tools,
)
from backend.app.retriever import RetrieverError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    include_sources: bool = True

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank.")
        return question


@lru_cache(maxsize=1)
def get_default_agent() -> EnterpriseAgent:
    return EnterpriseAgent(
        rag_service=get_default_rag_service(),
        sql_tools=get_default_sql_tools(),
    )


def get_agent() -> EnterpriseAgent:
    try:
        return get_default_agent()
    except (SQLToolUnavailableError, RetrieverError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The agent data services are unavailable.",
        ) from exc


@router.post("/ask", response_model=AgentResponse)
def ask_agent(
    request: AgentAskRequest,
    user: AuthUser = Depends(require_auth),
    agent: EnterpriseAgent = Depends(get_agent),
) -> AgentResponse:
    allowed_document_ids = get_visible_document_ids_for_user(user)
    try:
        return agent.ask(
            request.question,
            include_sources=request.include_sources,
            allowed_document_ids=allowed_document_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The agent question is invalid.",
        ) from exc
    except AgentWorkflowError as exc:
        logger.error("Agent workflow could not complete: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The agent workflow could not be completed.",
        ) from exc
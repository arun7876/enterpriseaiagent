from pathlib import Path

import pytest

from backend.app.agent_graph import (
    EnterpriseAgent,
    _requested_department,
    _document_search_query,
    choose_sql_tool,
    choose_workflow,
)
from backend.app.rag_service import (
    Citation,
    LLMUnavailableError,
    RAGAnswer,
)
from backend.app.sql_tools import BusinessSQLTools


class FakeLLM:
    model_name = "mock-local-model"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise LLMUnavailableError("mock model unavailable")
        return "Sales were $5,050.00 and the report describes the policy [S1]. [S99]"


class FakeRAGService:
    def __init__(self, fail: bool = False, sufficient: bool = True, llm_fail: bool = False) -> None:
        self.fail = fail
        self.sufficient = sufficient
        self.llm_client = FakeLLM(fail=llm_fail)
        self.calls: list[str] = []

    def ask(self, question: str, document_ids: list[str] | None = None) -> RAGAnswer:
        self.calls.append(question)
        if self.fail:
            raise LLMUnavailableError("mock RAG model unavailable")
        citations = (
            [
                Citation(
                    source_id="S1",
                    document_id="doc-policy",
                    chunk_id="chunk-policy",
                    filename="annual-policy.pdf",
                    chunk_index=2,
                    page_number=3,
                    excerpt="Employees receive annual paid leave.",
                    relevance_score=0.82,
                    metadata={"page_number": 3},
                )
            ]
            if self.sufficient
            else []
        )
        return RAGAnswer(
            answer=(
                "Employees receive annual paid leave [S1]."
                if self.sufficient
                else "The indexed documents do not provide enough evidence to answer this question."
            ),
            citations=citations,
            source_filenames=["annual-policy.pdf"] if citations else [],
            retrieval_count=len(citations),
            model_identifier=self.llm_client.model_name,
            processing_time_ms=2,
        )


def make_agent(
    tmp_path: Path,
    *,
    rag_fail: bool = False,
    rag_sufficient: bool = True,
    llm_fail: bool = False,
) -> tuple[EnterpriseAgent, FakeRAGService]:
    rag = FakeRAGService(fail=rag_fail, sufficient=rag_sufficient, llm_fail=llm_fail)
    return EnterpriseAgent(rag, BusinessSQLTools(tmp_path / "business.sqlite3")), rag


def test_deterministic_workflow_and_sql_tool_routing() -> None:
    assert choose_workflow("What is the annual leave policy?") == "document_search"
    assert choose_workflow("What were total sales last month?") == "sql_analytics"
    assert choose_workflow(
        "Compare sales across departments and explain the uploaded sales report."
    ) == "combined"
    assert choose_sql_tool("Compare sales across departments") == "sales_by_department"
    assert choose_sql_tool("How many employees are in Sales?") == "employee_counts_by_department"
    assert _requested_department("What were total sales last month?") is None
    assert _requested_department("How much did the Sales department sell?") == "Sales"


def test_combined_document_search_uses_a_focused_report_query() -> None:
    query = _document_search_query(
        {
            "question": "Compare sales across departments and explain using the report.",
            "workflow": "combined",
            "sql_tool_name": "sales_by_department",
            "sql_arguments": {
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
            },
        }
    )

    assert query == "September 2026 sales report department totals"


def test_document_only_question_uses_existing_rag_service(tmp_path: Path) -> None:
    agent, rag = make_agent(tmp_path)

    result = agent.ask("What is the annual leave policy?")

    assert result.workflow == "document_search"
    assert result.selected_tools == ["document_search"]
    assert result.answer == "Employees receive annual paid leave [S1]."
    assert result.citations[0].filename == "annual-policy.pdf"
    assert result.citations[0].page_number == 3
    assert result.sufficient_evidence
    assert rag.calls == ["What is the annual leave policy?"]


def test_sql_only_question_uses_real_sales_aggregate(tmp_path: Path) -> None:
    agent, rag = make_agent(tmp_path)

    result = agent.ask("What were total sales from 2026-09-01 to 2026-09-30?")

    assert result.workflow == "sql_analytics"
    assert result.selected_tools == ["business_data.total_sales"]
    assert "5,050.00" in result.answer
    assert result.structured_data[0]["rows"][0]["total_amount_usd"] == 5050.0
    assert result.citations == []
    assert result.sufficient_evidence
    assert rag.calls == []


def test_employee_question_uses_department_count_tool(tmp_path: Path) -> None:
    agent, _ = make_agent(tmp_path)

    result = agent.ask("How many employees are in the Sales department?")

    assert result.selected_tools == ["business_data.employee_counts_by_department"]
    assert "Sales: 3 employees" in result.answer
    assert result.structured_data[0]["rows"] == [
        {"department": "Sales", "employee_count": 3}
    ]


def test_combined_question_uses_both_tools_and_synthesizes_real_results(
    tmp_path: Path,
) -> None:
    agent, rag = make_agent(tmp_path)

    result = agent.ask(
        "Compare sales across departments and explain the uploaded sales report "
        "from 2026-09-01 to 2026-09-30."
    )

    assert result.workflow == "combined"
    assert result.selected_tools == ["document_search", "business_data.sales_by_department"]
    assert result.structured_data[0]["row_count"] == 3
    assert result.citations[0].filename == "annual-policy.pdf"
    assert "[S1]" in result.answer
    assert "Sales: $3,500.00 USD" in result.answer
    assert "Engineering: $900.00 USD (1 sale)" in result.answer
    assert "Operations: $650.00 USD (1 sale)" in result.answer
    assert result.sufficient_evidence
    assert rag.calls == ["September 2026 sales report department totals"]


def test_invalid_dates_return_clear_error_without_fabricated_result(
    tmp_path: Path,
) -> None:
    agent, _ = make_agent(tmp_path)

    result = agent.ask("What were sales from 2026-02-31 to 2026-03-01?")

    assert result.workflow == "sql_analytics"
    assert result.structured_data == []
    assert not result.sufficient_evidence
    assert result.errors == ["Business-data request rejected: start_date must be an ISO date (YYYY-MM-DD)."]


def test_no_matching_business_rows_is_reported_as_insufficient(
    tmp_path: Path,
) -> None:
    agent, _ = make_agent(tmp_path)

    result = agent.ask("What were sales from 2024-01-01 to 2024-01-31?")

    assert "No sales records" in result.answer
    assert not result.sufficient_evidence


def test_local_rag_model_failure_is_returned_as_a_tool_error(
    tmp_path: Path,
) -> None:
    agent, _ = make_agent(tmp_path, rag_fail=True)

    result = agent.ask("What is the annual leave policy?")

    assert not result.sufficient_evidence
    assert result.errors == [
        "Document answer generation is unavailable because the local model failed."
    ]


def test_combined_document_failure_returns_sql_result_and_error(
    tmp_path: Path,
) -> None:
    agent, _ = make_agent(tmp_path, rag_fail=True)

    result = agent.ask(
        "Compare sales across departments and explain the uploaded report "
        "from 2026-09-01 to 2026-09-30."
    )

    assert not result.sufficient_evidence
    assert "Sales: $3,500.00 USD" in result.answer
    assert "Document evidence was unavailable" in result.answer
    assert any("local model failed" in error for error in result.errors)


def test_include_sources_false_hides_citations_but_keeps_answer(tmp_path: Path) -> None:
    agent, _ = make_agent(tmp_path)

    result = agent.ask("What is the annual leave policy?", include_sources=False)

    assert result.answer == "Employees receive annual paid leave."
    assert result.citations == []
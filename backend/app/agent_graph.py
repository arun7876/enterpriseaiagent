import logging
import re
import time
import calendar
from datetime import date, timedelta
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from backend.app.rag_service import (
    Citation,
    LLMUnavailableError,
    RAGService,
)
from backend.app.retriever import RetrieverError
from backend.app.sql_tools import (
    BusinessSQLTools,
    SQLToolError,
    SQLToolResult,
    SQLToolUnavailableError,
)


logger = logging.getLogger(__name__)
AgentWorkflow = Literal["document_search", "sql_analytics", "combined"]


class AgentState(TypedDict, total=False):
    question: str
    include_sources: bool
    allowed_document_ids: list[str] | None
    workflow: AgentWorkflow
    sql_tool_name: str
    sql_arguments: dict[str, Any]
    sql_answer: str
    sql_sufficient_evidence: bool
    selected_tools: list[str]
    document_result: dict[str, Any]
    structured_results: list[dict[str, Any]]
    errors: list[str]
    answer: str
    sufficient_evidence: bool


class AgentResponse(BaseModel):
    answer: str
    workflow: AgentWorkflow
    selected_tools: list[str]
    structured_data: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    sufficient_evidence: bool
    processing_time_ms: float
    errors: list[str] = Field(default_factory=list)


class AgentWorkflowError(RuntimeError):
    """Raised when the controlled workflow itself cannot be executed."""


DOCUMENT_SIGNALS = (
    "policy",
    "document",
    "uploaded",
    "report",
    "handbook",
    "contract",
    "pdf",
    "docx",
    "according to",
    "what does",
)
SQL_SIGNALS = (
    "sales",
    "revenue",
    "employee",
    "employees",
    "headcount",
    "department",
    "departments",
    "transaction",
    "transactions",
)
INSUFFICIENT_DATA_ANSWER = "The available tools did not return enough supporting evidence."


def resolve_date_range(question: str, today: date | None = None) -> tuple[str, str]:
    current_date = today or date.today()
    explicit_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question)
    if len(explicit_dates) >= 2:
        return explicit_dates[0], explicit_dates[1]
    if explicit_dates:
        return explicit_dates[0], explicit_dates[0]

    lowered = question.casefold()
    if "last month" in lowered or "previous month" in lowered:
        first_of_current_month = current_date.replace(day=1)
        last_of_previous_month = first_of_current_month - timedelta(days=1)
        first_of_previous_month = last_of_previous_month.replace(day=1)
        return first_of_previous_month.isoformat(), last_of_previous_month.isoformat()
    if "this month" in lowered or "current month" in lowered:
        return current_date.replace(day=1).isoformat(), current_date.isoformat()
    if "last year" in lowered or "previous year" in lowered:
        return f"{current_date.year - 1:04d}-01-01", f"{current_date.year - 1:04d}-12-31"
    return "0001-01-01", "9999-12-31"


def choose_workflow(question: str) -> AgentWorkflow:
    lowered = question.casefold()
    needs_documents = any(signal in lowered for signal in DOCUMENT_SIGNALS)
    needs_sql = any(signal in lowered for signal in SQL_SIGNALS)
    if needs_documents and needs_sql:
        return "combined"
    if needs_sql:
        return "sql_analytics"
    return "document_search"


def choose_sql_tool(question: str) -> str:
    lowered = question.casefold()
    if "employee" in lowered or "headcount" in lowered:
        return "employee_counts_by_department"
    if any(term in lowered for term in ("transaction", "transactions", "list sales")):
        return "list_sales_transactions"
    if any(term in lowered for term in ("compare", "by department", "across department", "group")):
        return "sales_by_department"
    return "total_sales"


def _requested_department(question: str) -> str | None:
    lowered = question.casefold()
    for name in ("Sales", "Engineering", "Operations"):
        escaped_name = re.escape(name.casefold())
        department_reference = (
            rf"\b(?:in|for|within)\s+(?:the\s+)?{escaped_name}(?:\s+department)?\b"
            rf"|\b{escaped_name}\s+department\b"
            rf"|\bdepartment\s+(?:of\s+)?{escaped_name}\b"
        )
        if re.search(department_reference, lowered):
            return name
    return None


def _sql_tool_arguments(question: str, tool_name: str) -> dict[str, Any]:
    department = _requested_department(question)
    if tool_name == "employee_counts_by_department":
        return {"department": department}
    if tool_name == "list_sales_transactions":
        start_date, end_date = resolve_date_range(question)
        return {
            "start_date": start_date,
            "end_date": end_date,
            "department": department,
            "limit": 50,
        }
    if tool_name == "sales_by_department":
        start_date, end_date = resolve_date_range(question)
        return {"start_date": start_date, "end_date": end_date}
    start_date, end_date = resolve_date_range(question)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "department": department,
    }


def _document_search_query(state: AgentState) -> str:
    if state.get("workflow") != "combined":
        return state["question"]

    tool_name = state.get("sql_tool_name")
    query_terms = {
        "sales_by_department": "sales report department totals",
        "total_sales": "sales report total sales",
        "employee_counts_by_department": "employee report employee counts by department",
        "list_sales_transactions": "sales report transactions",
    }.get(tool_name)
    if query_terms is None:
        return state["question"]

    arguments = state.get("sql_arguments", {})
    start_value = arguments.get("start_date")
    end_value = arguments.get("end_date")
    if not isinstance(start_value, str) or not isinstance(end_value, str):
        return query_terms
    try:
        start = date.fromisoformat(start_value)
        end = date.fromisoformat(end_value)
    except ValueError:
        return query_terms

    if (
        start.year == end.year
        and start.month == end.month
        and start.day == 1
        and end.day == calendar.monthrange(end.year, end.month)[1]
    ):
        period = f"{calendar.month_name[start.month]} {start.year}"
    elif (start_value, end_value) != ("0001-01-01", "9999-12-31"):
        period = f"{start_value} {end_value}"
    else:
        period = ""
    return f"{period} {query_terms}".strip()


def _sql_answer(result: SQLToolResult) -> tuple[str, bool]:
    if result.tool_name == "total_sales":
        row = result.rows[0]
        sale_count = int(row["sale_count"])
        if sale_count == 0:
            return "No sales records were found for the requested period.", False
        amount = float(row["total_amount_usd"])
        return f"Total sales were ${amount:,.2f} USD across {sale_count} sales records.", True

    if result.tool_name == "sales_by_department":
        if not any(int(row["sale_count"]) for row in result.rows):
            return "No sales records were found for the requested period.", False
        summaries: list[str] = []
        for row in result.rows:
            sale_count = int(row["sale_count"])
            sale_label = "sale" if sale_count == 1 else "sales"
            summaries.append(
                f"{row['department']}: ${float(row['total_amount_usd']):,.2f} USD "
                f"({sale_count} {sale_label})"
            )
        return "Sales by department: " + "; ".join(summaries) + ".", True

    if result.tool_name == "employee_counts_by_department":
        summaries = [
            f"{row['department']}: {int(row['employee_count'])} employees"
            for row in result.rows
        ]
        if not summaries:
            return "No employee counts were available.", False
        return "Employee counts by department: " + "; ".join(summaries) + ".", True

    if result.tool_name == "list_sales_transactions":
        if not result.rows:
            return "No sales records were found for the requested period.", False
        return result.summary + f" Returned {result.row_count} rows.", True

    return result.summary, result.row_count > 0


class EnterpriseAgent:
    def __init__(self, rag_service: RAGService, sql_tools: BusinessSQLTools) -> None:
        self.rag_service = rag_service
        self.sql_tools = sql_tools
        builder = StateGraph(AgentState)
        builder.add_node("classify", self._classify)
        builder.add_node("document_search", self._document_search)
        builder.add_node("sql_query", self._sql_query)
        builder.add_node("synthesize", self._synthesize)
        builder.add_edge(START, "classify")
        builder.add_conditional_edges(
            "classify",
            self._after_classification,
            {"document_search": "document_search", "sql_query": "sql_query"},
        )
        builder.add_conditional_edges(
            "document_search",
            self._after_document_search,
            {"sql_query": "sql_query", "synthesize": "synthesize"},
        )
        builder.add_edge("sql_query", "synthesize")
        builder.add_edge("synthesize", END)
        self.graph = builder.compile()

    def _classify(self, state: AgentState) -> dict[str, Any]:
        question = state["question"]
        workflow = choose_workflow(question)
        selected_tools: list[str] = []
        result: dict[str, Any] = {
            "workflow": workflow,
            "selected_tools": selected_tools,
            "errors": [],
            "structured_results": [],
        }
        if workflow in {"document_search", "combined"}:
            selected_tools.append("document_search")
        if workflow in {"sql_analytics", "combined"}:
            tool_name = choose_sql_tool(question)
            result["sql_tool_name"] = tool_name
            result["sql_arguments"] = _sql_tool_arguments(question, tool_name)
            selected_tools.append(f"business_data.{tool_name}")
        return result

    @staticmethod
    def _after_classification(state: AgentState) -> str:
        return "sql_query" if state["workflow"] == "sql_analytics" else "document_search"

    @staticmethod
    def _after_document_search(state: AgentState) -> str:
        return "sql_query" if state["workflow"] == "combined" else "synthesize"

    def _document_search(self, state: AgentState) -> dict[str, Any]:
        try:
            answer = self.rag_service.ask(
                _document_search_query(state),
                document_ids=state.get("allowed_document_ids"),
            )
            return {"document_result": answer.model_dump(mode="json")}
        except LLMUnavailableError:
            message = "Document answer generation is unavailable because the local model failed."
        except RetrieverError:
            message = "Document retrieval is unavailable because the local index failed."
        except ValueError:
            message = "The document search request was invalid."
        return {"document_result": None, "errors": [*state.get("errors", []), message]}

    def _sql_query(self, state: AgentState) -> dict[str, Any]:
        tool_name = state["sql_tool_name"]
        try:
            result = self.sql_tools.execute_tool(tool_name, state["sql_arguments"])
            structured = result.model_dump(mode="json")
            answer, sufficient = _sql_answer(result)
            return {
                "structured_results": [structured],
                "sql_answer": answer,
                "sql_sufficient_evidence": sufficient,
            }
        except SQLToolError as exc:
            message = f"Business-data request rejected: {exc}"
        except SQLToolUnavailableError:
            message = "The business-data tool is unavailable."
        return {"structured_results": [], "sql_answer": "", "sql_sufficient_evidence": False, "errors": [*state.get("errors", []), message]}

    def _synthesize(self, state: AgentState) -> dict[str, Any]:
        workflow = state["workflow"]
        document_result = state.get("document_result")
        structured_results = state.get("structured_results", [])
        errors = list(state.get("errors", []))
        document_sufficient = bool(
            document_result and int(document_result.get("retrieval_count", 0)) > 0
        )
        sql_sufficient = bool(state.get("sql_sufficient_evidence", False))

        if workflow == "document_search":
            if document_result is None:
                answer = "Document search failed; no document-grounded answer is available."
            else:
                answer = str(document_result["answer"])
            return {
                "answer": answer,
                "sufficient_evidence": document_sufficient,
                "errors": errors,
            }

        sql_answer = str(state.get("sql_answer", ""))
        if workflow == "sql_analytics":
            answer = sql_answer or "The business-data query could not be completed."
            return {
                "answer": answer,
                "sufficient_evidence": sql_sufficient,
                "errors": errors,
            }

        if document_result is None:
            if sql_answer:
                answer = sql_answer + " Document evidence was unavailable."
            else:
                answer = "Neither document nor business-data evidence was available."
            return {"answer": answer, "sufficient_evidence": False, "errors": errors}

        if not document_sufficient:
            errors.append("No relevant document passage was retrieved for the combined question.")
        if not sql_sufficient:
            errors.append("The business-data tools returned no supporting records.")

        document_answer = str(document_result["answer"])
        if sql_answer and document_sufficient:
            answer = f"{sql_answer}\n\nDocument evidence: {document_answer}"
        elif sql_answer:
            answer = (
                f"{sql_answer}\n\nDocument evidence is insufficient: "
                f"{document_answer}"
            )
        elif document_sufficient:
            answer = (
                f"{document_answer}\n\nBusiness-data evidence could not be completed."
            )
        else:
            answer = INSUFFICIENT_DATA_ANSWER

        return {
            "answer": answer,
            "sufficient_evidence": document_sufficient and sql_sufficient,
            "errors": errors,
        }

    def ask(
        self,
        question: str,
        include_sources: bool = True,
        allowed_document_ids: list[str] | None = None,
    ) -> AgentResponse:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be blank.")
        started_at = time.perf_counter()
        try:
            state = self.graph.invoke(
                {
                    "question": normalized_question,
                    "include_sources": include_sources,
                    "allowed_document_ids": allowed_document_ids,
                },
                config={"recursion_limit": 8},
            )
        except Exception as exc:
            logger.exception("The enterprise agent graph failed.")
            raise AgentWorkflowError("The agent workflow could not be completed.") from exc

        document_result = state.get("document_result") or {}
        citations = (
            [Citation.model_validate(item) for item in document_result.get("citations", [])]
            if include_sources
            else []
        )
        answer = state.get("answer", INSUFFICIENT_DATA_ANSWER)
        if not include_sources:
            answer = re.sub(r"\s*\[S\d+\]", "", answer).strip()
        return AgentResponse(
            answer=answer,
            workflow=state.get("workflow", "document_search"),
            selected_tools=state.get("selected_tools", []),
            structured_data=state.get("structured_results", []),
            citations=citations,
            sufficient_evidence=bool(state.get("sufficient_evidence", False)),
            processing_time_ms=(time.perf_counter() - started_at) * 1000,
            errors=state.get("errors", []),
        )
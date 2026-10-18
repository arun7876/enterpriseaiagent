import sqlite3
from pathlib import Path

import pytest

from backend.app.retriever import DEFAULT_INDEX_PATH
from backend.app.sql_tools import (
    BusinessSQLTools,
    MAX_RESULT_ROWS,
    SQLToolError,
)


@pytest.fixture
def sql_tools(tmp_path: Path) -> BusinessSQLTools:
    return BusinessSQLTools(tmp_path / "business.sqlite3")


def test_business_database_is_separate_and_lists_only_allowlisted_schema(
    sql_tools: BusinessSQLTools,
) -> None:
    result = sql_tools.list_tables()

    assert sql_tools.database_path != DEFAULT_INDEX_PATH
    assert {row["table_name"] for row in result.rows} == {
        "sales",
        "departments",
        "employees",
    }
    assert "sqlite_master" not in {row["table_name"] for row in result.rows}


def test_total_sales_uses_a_validated_date_range(sql_tools: BusinessSQLTools) -> None:
    result = sql_tools.total_sales("2026-09-01", "2026-09-30")

    assert result.rows == [{"total_amount_usd": 5050.0, "sale_count": 4}]
    assert result.parameters["start_date"] == "2026-09-01"


def test_department_sales_grouping_returns_expected_totals(
    sql_tools: BusinessSQLTools,
) -> None:
    result = sql_tools.sales_by_department("2026-09-01", "2026-09-30")

    assert result.rows == [
        {"department": "Sales", "total_amount_usd": 3500.0, "sale_count": 2},
        {"department": "Engineering", "total_amount_usd": 900.0, "sale_count": 1},
        {"department": "Operations", "total_amount_usd": 650.0, "sale_count": 1},
    ]


def test_employee_counts_by_department(sql_tools: BusinessSQLTools) -> None:
    result = sql_tools.employee_counts_by_department()

    assert {row["department"]: row["employee_count"] for row in result.rows} == {
        "Sales": 3,
        "Engineering": 2,
        "Operations": 2,
    }


def test_invalid_dates_and_date_injection_are_rejected_without_modifying_rows(
    sql_tools: BusinessSQLTools,
) -> None:
    before = sql_tools.total_sales("2026-01-01", "2026-12-31").rows

    with pytest.raises(SQLToolError, match="ISO date"):
        sql_tools.total_sales("2026-09-01'; DROP TABLE sales;--", "2026-09-30")
    with pytest.raises(SQLToolError, match="ISO date"):
        sql_tools.total_sales("2026-02-30", "2026-09-30")

    assert sql_tools.total_sales("2026-01-01", "2026-12-31").rows == before


def test_unauthorized_tables_columns_and_arbitrary_sql_are_rejected(
    sql_tools: BusinessSQLTools,
) -> None:
    with pytest.raises(SQLToolError, match="not permitted"):
        sql_tools.describe_table("sqlite_master")
    with pytest.raises(SQLToolError, match="not permitted"):
        sql_tools.execute_tool("run_sql", {"sql": "SELECT * FROM sqlite_master"})
    with pytest.raises(SQLToolError, match="invalid"):
        sql_tools.execute_tool("total_sales", {"start_date": "2026-09-01", "end_date": "2026-09-30", "column": "secret"})


def test_transaction_listing_has_a_hard_result_limit(
    sql_tools: BusinessSQLTools,
) -> None:
    with pytest.raises(SQLToolError, match="limit must be between"):
        sql_tools.list_sales_transactions("2026-01-01", "2026-12-31", limit=MAX_RESULT_ROWS + 1)

    result = sql_tools.list_sales_transactions(
        "2026-01-01",
        "2026-12-31",
        limit=MAX_RESULT_ROWS,
    )
    assert result.row_count <= MAX_RESULT_ROWS


def test_read_connections_cannot_write_or_delete(sql_tools: BusinessSQLTools) -> None:
    with sql_tools._read_connection() as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM sales")

    assert sql_tools.total_sales("2026-09-01", "2026-09-30").rows[0]["sale_count"] == 4


def test_execute_tool_dispatches_only_known_structured_arguments(
    sql_tools: BusinessSQLTools,
) -> None:
    result = sql_tools.execute_tool(
        "total_sales",
        {"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )

    assert result.tool_name == "total_sales"
    assert result.rows[0]["total_amount_usd"] == 5050.0
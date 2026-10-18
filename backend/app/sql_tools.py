import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.config import settings

logger = logging.getLogger(__name__)
DEFAULT_BUSINESS_DB_PATH = (
    settings.business_db_path
)
MAX_RESULT_ROWS = 100
PERMITTED_SCHEMA: dict[str, tuple[str, ...]] = {
    "departments": ("department_id", "name"),
    "employees": ("employee_id", "department_id", "job_title"),
    "sales": ("sale_id", "department_id", "sale_date", "amount_cents", "region"),
}


class SQLToolError(ValueError):
    """Raised when a requested business-data tool or argument is not allowed."""


class SQLToolUnavailableError(RuntimeError):
    """Raised when the local business analytics database cannot be used."""


class SQLToolResult(BaseModel):
    tool_name: str
    summary: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    parameters: dict[str, str | int | None] = Field(default_factory=dict)


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DateRangeArguments(ToolArguments):
    start_date: str
    end_date: str
    department: str | None = None


class DepartmentCountArguments(ToolArguments):
    department: str | None = None


class SalesRowsArguments(DateRangeArguments):
    department: str | None = None
    limit: int = Field(default=50, ge=1, le=MAX_RESULT_ROWS)


class BusinessSQLTools:
    """Predefined read-only business queries over a separate SQLite database."""

    def __init__(
        self,
        database_path: str | Path | None = None,
        query_timeout_seconds: float = 2.0,
    ) -> None:
        self.database_path = Path(
            database_path or DEFAULT_BUSINESS_DB_PATH
        )
        self.query_timeout_seconds = max(0.1, query_timeout_seconds)
        self._initialize_database()

    def _initialize_database(self) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.database_path), timeout=10) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS departments (
                        department_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE IF NOT EXISTS employees (
                        employee_id INTEGER PRIMARY KEY,
                        department_id INTEGER NOT NULL REFERENCES departments(department_id),
                        job_title TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sales (
                        sale_id INTEGER PRIMARY KEY,
                        department_id INTEGER NOT NULL REFERENCES departments(department_id),
                        sale_date TEXT NOT NULL,
                        amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
                        region TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS sales_date_department_idx
                        ON sales(sale_date, department_id);
                    """
                )
                self._seed_if_empty(connection)
        except (OSError, sqlite3.Error) as exc:
            logger.exception("Could not initialize the local business analytics database.")
            raise SQLToolUnavailableError(
                "The local business analytics database is unavailable."
            ) from exc

    @staticmethod
    def _seed_if_empty(connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] > 0:
            return
        connection.executemany(
            "INSERT OR IGNORE INTO departments(department_id, name) VALUES (?, ?)",
            [(1, "Sales"), (2, "Engineering"), (3, "Operations")],
        )
        connection.executemany(
            "INSERT OR IGNORE INTO employees(employee_id, department_id, job_title) "
            "VALUES (?, ?, ?)",
            [
                (1, 1, "Account Executive"),
                (2, 1, "Sales Analyst"),
                (3, 1, "Sales Manager"),
                (4, 2, "Software Engineer"),
                (5, 2, "Data Engineer"),
                (6, 3, "Operations Analyst"),
                (7, 3, "Operations Manager"),
            ],
        )
        connection.executemany(
            "INSERT OR IGNORE INTO sales "
            "(sale_id, department_id, sale_date, amount_cents, region) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, "2026-09-03", 125000, "North"),
                (2, 1, "2026-09-12", 225000, "West"),
                (3, 2, "2026-09-14", 90000, "North"),
                (4, 3, "2026-09-22", 65000, "East"),
                (5, 1, "2026-08-08", 50000, "West"),
                (6, 2, "2026-08-28", 75000, "North"),
                (7, 3, "2026-08-30", 40000, "East"),
                (8, 1, "2026-10-02", 175000, "South"),
            ],
        )

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            database_uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(
                database_uri,
                uri=True,
                timeout=self.query_timeout_seconds,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            deadline = time.monotonic() + self.query_timeout_seconds
            connection.set_progress_handler(
                lambda: int(time.monotonic() >= deadline),
                1000,
            )
            yield connection
        except sqlite3.Error as exc:
            logger.exception("A predefined business-data query failed.")
            raise SQLToolUnavailableError(
                "The requested business-data query could not be completed."
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _parse_date(value: str, parameter_name: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise SQLToolError(f"{parameter_name} must be an ISO date (YYYY-MM-DD).") from exc
        if parsed.isoformat() != value:
            raise SQLToolError(f"{parameter_name} must be an ISO date (YYYY-MM-DD).")
        return value

    @classmethod
    def _validate_date_range(cls, start_date: str, end_date: str) -> tuple[str, str]:
        start = cls._parse_date(start_date, "start_date")
        end = cls._parse_date(end_date, "end_date")
        if start > end:
            raise SQLToolError("start_date must be on or before end_date.")
        return start, end

    def _validate_department(self, department: str | None) -> str | None:
        if department is None:
            return None
        if not isinstance(department, str) or len(department) > 80:
            raise SQLToolError("department is not permitted.")
        with self._read_connection() as connection:
            rows = connection.execute("SELECT name FROM departments").fetchall()
        permitted = {str(row["name"]).casefold(): str(row["name"]) for row in rows}
        canonical = permitted.get(department.casefold())
        if canonical is None:
            raise SQLToolError("department is not permitted.")
        return canonical

    def list_tables(self) -> SQLToolResult:
        rows = [
            {"table_name": table_name, "columns": list(columns)}
            for table_name, columns in PERMITTED_SCHEMA.items()
        ]
        return SQLToolResult(
            tool_name="list_tables",
            summary="Lists only the business tables and columns approved for this agent.",
            columns=["table_name", "columns"],
            rows=rows,
            row_count=len(rows),
        )

    def describe_table(self, table_name: str) -> SQLToolResult:
        if table_name not in PERMITTED_SCHEMA:
            raise SQLToolError("table_name is not permitted.")
        columns = list(PERMITTED_SCHEMA[table_name])
        return SQLToolResult(
            tool_name="describe_table",
            summary=f"Lists the permitted columns for {table_name}.",
            columns=["table_name", "column_name"],
            rows=[{"table_name": table_name, "column_name": column} for column in columns],
            row_count=len(columns),
            parameters={"table_name": table_name},
        )

    def total_sales(
        self,
        start_date: str,
        end_date: str,
        department: str | None = None,
    ) -> SQLToolResult:
        start, end = self._validate_date_range(start_date, end_date)
        department_name = self._validate_department(department)
        query = (
            "SELECT COALESCE(SUM(s.amount_cents), 0) AS total_cents, COUNT(*) AS sale_count "
            "FROM sales AS s JOIN departments AS d ON d.department_id = s.department_id "
            "WHERE s.sale_date BETWEEN ? AND ?"
        )
        parameters: list[str] = [start, end]
        if department_name is not None:
            query += " AND d.name = ?"
            parameters.append(department_name)
        with self._read_connection() as connection:
            row = connection.execute(query, parameters).fetchone()
        total_cents = int(row["total_cents"])
        sale_count = int(row["sale_count"])
        return SQLToolResult(
            tool_name="total_sales",
            summary=f"Total synthetic sales were ${total_cents / 100:,.2f} USD across {sale_count} records.",
            columns=["total_amount_usd", "sale_count"],
            rows=[{"total_amount_usd": total_cents / 100, "sale_count": sale_count}],
            row_count=1,
            parameters={
                "start_date": start,
                "end_date": end,
                "department": department_name,
            },
        )

    def sales_by_department(self, start_date: str, end_date: str) -> SQLToolResult:
        start, end = self._validate_date_range(start_date, end_date)
        query = (
            "SELECT d.name AS department, "
            "COALESCE(SUM(s.amount_cents), 0) / 100.0 AS total_amount_usd, "
            "COUNT(s.sale_id) AS sale_count "
            "FROM departments AS d LEFT JOIN sales AS s "
            "ON s.department_id = d.department_id AND s.sale_date BETWEEN ? AND ? "
            "GROUP BY d.department_id, d.name ORDER BY total_amount_usd DESC, d.name ASC "
            "LIMIT ?"
        )
        with self._read_connection() as connection:
            rows = connection.execute(query, (start, end, MAX_RESULT_ROWS)).fetchall()
        result_rows = [dict(row) for row in rows]
        return SQLToolResult(
            tool_name="sales_by_department",
            summary=f"Sales by department from {start} through {end} (USD).",
            columns=["department", "total_amount_usd", "sale_count"],
            rows=result_rows,
            row_count=len(result_rows),
            parameters={"start_date": start, "end_date": end},
        )

    def employee_counts_by_department(
        self,
        department: str | None = None,
    ) -> SQLToolResult:
        department_name = self._validate_department(department)
        query = (
            "SELECT d.name AS department, COUNT(e.employee_id) AS employee_count "
            "FROM departments AS d LEFT JOIN employees AS e "
            "ON e.department_id = d.department_id"
        )
        parameters: tuple[str, ...] = ()
        if department_name is not None:
            query += " WHERE d.name = ?"
            parameters = (department_name,)
        query += " GROUP BY d.department_id, d.name ORDER BY d.name LIMIT ?"
        with self._read_connection() as connection:
            rows = connection.execute(query, (*parameters, MAX_RESULT_ROWS)).fetchall()
        result_rows = [dict(row) for row in rows]
        return SQLToolResult(
            tool_name="employee_counts_by_department",
            summary="Synthetic employee counts by department.",
            columns=["department", "employee_count"],
            rows=result_rows,
            row_count=len(result_rows),
            parameters={"department": department_name},
        )

    def list_sales_transactions(
        self,
        start_date: str,
        end_date: str,
        department: str | None = None,
        limit: int = 50,
    ) -> SQLToolResult:
        start, end = self._validate_date_range(start_date, end_date)
        department_name = self._validate_department(department)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_RESULT_ROWS:
            raise SQLToolError(f"limit must be between 1 and {MAX_RESULT_ROWS}.")
        query = (
            "SELECT s.sale_id, d.name AS department, s.sale_date, "
            "s.amount_cents / 100.0 AS amount_usd, s.region "
            "FROM sales AS s JOIN departments AS d ON d.department_id = s.department_id "
            "WHERE s.sale_date BETWEEN ? AND ?"
        )
        parameters: list[str | int] = [start, end]
        if department_name is not None:
            query += " AND d.name = ?"
            parameters.append(department_name)
        query += " ORDER BY s.sale_date, s.sale_id LIMIT ?"
        parameters.append(limit)
        with self._read_connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        result_rows = [dict(row) for row in rows]
        return SQLToolResult(
            tool_name="list_sales_transactions",
            summary=f"At most {limit} sales transactions from {start} through {end} (USD).",
            columns=["sale_id", "department", "sale_date", "amount_usd", "region"],
            rows=result_rows,
            row_count=len(result_rows),
            parameters={
                "start_date": start,
                "end_date": end,
                "department": department_name,
                "limit": limit,
            },
        )

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> SQLToolResult:
        """Dispatch only approved named tools; raw SQL is never accepted."""
        tools: dict[str, tuple[type[ToolArguments], Any]] = {
            "list_tables": (ToolArguments, lambda _: self.list_tables()),
            "describe_table": (DescribeTableArguments, lambda args: self.describe_table(args.table_name)),
            "total_sales": (DateRangeArguments, lambda args: self.total_sales(args.start_date, args.end_date, args.department)),
            "sales_by_department": (DateRangeArguments, lambda args: self.sales_by_department(args.start_date, args.end_date)),
            "employee_counts_by_department": (
                DepartmentCountArguments,
                lambda args: self.employee_counts_by_department(args.department),
            ),
            "list_sales_transactions": (
                SalesRowsArguments,
                lambda args: self.list_sales_transactions(
                    args.start_date, args.end_date, args.department, args.limit
                ),
            ),
        }
        specification = tools.get(tool_name)
        if specification is None:
            raise SQLToolError("The requested business-data tool is not permitted.")
        argument_model, handler = specification
        try:
            parsed_arguments = argument_model.model_validate(arguments)
        except ValidationError as exc:
            raise SQLToolError("The business-data tool arguments are invalid.") from exc
        return handler(parsed_arguments)


class DescribeTableArguments(ToolArguments):
    table_name: str


def get_default_sql_tools() -> BusinessSQLTools:
    return BusinessSQLTools()
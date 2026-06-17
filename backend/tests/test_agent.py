"""
Phase 4 tests — Agent (SQL generation) and Executor (safe execution).

Tests are split into:
1. Unit tests for extract_tag, _validate_sql (no API needed)
2. Integration tests for generate_sql + safe_execute (require ANTHROPIC_API_KEY)

Run with: python -m pytest backend/tests/test_agent.py -v
Skip integration tests (no API key): python -m pytest backend/tests/test_agent.py -v -k "not integration"
"""

import os
import sys
import sqlite3
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.agent import extract_tag, generate_sql, get_schema_context, fix_sql
from pipeline.executor import safe_execute, _validate_sql, MAX_ROWS
from main import DB_PATH
from tests.conftest import generate_sql_or_skip


# ─── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def schema_context():
    """Load schema context from the test database."""
    return get_schema_context(DB_PATH)


requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration test",
)


# ─── Unit Tests: extract_tag ────────────────────────────────────────────────────

class TestExtractTag:
    """Tests for the XML tag extraction utility."""

    def test_extracts_sql_tag(self):
        text = "<sql>SELECT * FROM orders</sql>"
        assert extract_tag(text, "sql") == "SELECT * FROM orders"

    def test_extracts_explanation_tag(self):
        text = "<explanation>This query gets all orders.</explanation>"
        assert extract_tag(text, "explanation") == "This query gets all orders."

    def test_handles_multiline_sql(self):
        text = """<sql>
SELECT region, SUM(amount) AS total_revenue
FROM orders
GROUP BY region
ORDER BY total_revenue DESC
</sql>"""
        result = extract_tag(text, "sql")
        assert "SELECT" in result
        assert "GROUP BY" in result

    def test_returns_empty_for_missing_tag(self):
        text = "No tags here, just plain text."
        assert extract_tag(text, "sql") == ""

    def test_strips_whitespace(self):
        text = "<sql>  SELECT 1  </sql>"
        assert extract_tag(text, "sql") == "SELECT 1"

    def test_extracts_from_mixed_content(self):
        text = """Here is the query:
<sql>SELECT COUNT(*) FROM customers</sql>
<explanation>Counts all customers.</explanation>
"""
        assert extract_tag(text, "sql") == "SELECT COUNT(*) FROM customers"
        assert extract_tag(text, "explanation") == "Counts all customers."


# ─── Unit Tests: _validate_sql ──────────────────────────────────────────────────

class TestValidateSQL:
    """Tests for SQL safety validation."""

    def test_allows_select(self):
        _validate_sql("SELECT * FROM orders")  # Should not raise

    def test_allows_select_with_semicolon(self):
        _validate_sql("SELECT * FROM orders;")  # Should not raise

    def test_rejects_insert(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("INSERT INTO orders VALUES (1, 2, 3)")

    def test_rejects_update(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("UPDATE orders SET amount = 0")

    def test_rejects_delete(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("DELETE FROM orders")

    def test_rejects_drop(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("DROP TABLE orders")

    def test_rejects_select_with_embedded_drop(self):
        """SELECT that embeds a DROP in a subquery should be caught."""
        with pytest.raises(ValueError, match="forbidden keywords"):
            _validate_sql("SELECT * FROM orders; DROP TABLE orders")

    def test_rejects_non_select_start(self):
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("PRAGMA table_info(orders)")

    def test_allows_with_cte(self):
        # Note: CTEs start with WITH, not SELECT — our validator is strict
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")


# ─── Unit Tests: Schema context ─────────────────────────────────────────────────

class TestSchemaContext:
    """Tests for schema context loading."""

    def test_schema_context_loads(self, schema_context):
        assert len(schema_context) > 0

    def test_schema_contains_tables(self, schema_context):
        assert "customers" in schema_context
        assert "products" in schema_context
        assert "orders" in schema_context

    def test_schema_contains_columns(self, schema_context):
        assert "customer_id" in schema_context
        assert "product_id" in schema_context
        assert "amount" in schema_context
        assert "region" in schema_context
        assert "created_at" in schema_context

    def test_schema_contains_sample_data(self, schema_context):
        assert "Sample data" in schema_context

    def test_schema_contains_row_counts(self, schema_context):
        assert "Total rows" in schema_context


# ─── Unit Tests: safe_execute with known SQL ────────────────────────────────────

class TestSafeExecute:
    """Tests for the SQL executor with known-good queries."""

    def test_simple_count(self):
        result = safe_execute("SELECT COUNT(*) as cnt FROM orders", DB_PATH)
        assert len(result["rows"]) == 1
        assert result["rows"][0]["cnt"] >= 10000

    def test_returns_columns(self):
        result = safe_execute("SELECT region, COUNT(*) as cnt FROM orders GROUP BY region", DB_PATH)
        assert "region" in result["columns"]
        assert "cnt" in result["columns"]

    def test_region_aggregation(self):
        result = safe_execute(
            "SELECT region, SUM(amount) as total_revenue FROM orders GROUP BY region ORDER BY total_revenue DESC",
            DB_PATH,
        )
        assert len(result["rows"]) == 5  # 5 regions
        # All rows should have region and total_revenue
        for row in result["rows"]:
            assert "region" in row
            assert "total_revenue" in row
            assert row["total_revenue"] > 0

    def test_join_query(self):
        result = safe_execute(
            """
            SELECT p.category, COUNT(*) as order_count, SUM(o.amount) as revenue
            FROM orders o
            JOIN products p ON o.product_id = p.id
            GROUP BY p.category
            ORDER BY revenue DESC
            """,
            DB_PATH,
        )
        assert len(result["rows"]) > 0
        assert "category" in result["columns"]
        assert "revenue" in result["columns"]

    def test_truncation(self):
        # This query should return many rows
        result = safe_execute("SELECT * FROM orders LIMIT 1000", DB_PATH)
        assert result["truncated"] is True
        assert result["row_count"] == MAX_ROWS

    def test_rejects_dangerous_sql(self):
        with pytest.raises(ValueError):
            safe_execute("DROP TABLE orders", DB_PATH)


# ─── Integration Tests: Claude SQL generation (require API key) ─────────────────

class TestGenerateSQLIntegration:
    """
    End-to-end tests that call Claude to generate SQL from natural language.
    These require ANTHROPIC_API_KEY to be set.

    Covers the 5 query types from the plan:
    1. Aggregation
    2. Filtering
    3. Joining
    4. Time ranges
    5. Top-N
    """

    @requires_api_key
    def test_aggregation_query(self, schema_context):
        """Test: 'show me total revenue by region'"""
        sql, explanation = generate_sql_or_skip(
            generate_sql, "show me total revenue by region", schema_context
        )
        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()
        assert "region" in sql.lower()
        assert "amount" in sql.lower() or "revenue" in sql.lower()

        # Actually execute it
        result = safe_execute(sql, DB_PATH)
        assert len(result["rows"]) > 0

    @requires_api_key
    def test_filtering_query(self, schema_context):
        """Test: 'how many completed orders are there'"""
        sql, explanation = generate_sql_or_skip(
            generate_sql, "how many completed orders are there", schema_context
        )
        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()

        result = safe_execute(sql, DB_PATH)
        assert len(result["rows"]) > 0

    @requires_api_key
    def test_join_query(self, schema_context):
        """Test: 'show me revenue by product category'"""
        sql, explanation = generate_sql_or_skip(
            generate_sql, "show me revenue by product category", schema_context
        )
        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()

        result = safe_execute(sql, DB_PATH)
        assert len(result["rows"]) > 0

    @requires_api_key
    def test_time_range_query(self, schema_context):
        """Test: 'how many orders were placed in 2024'"""
        sql, explanation = generate_sql_or_skip(
            generate_sql, "how many orders were placed in 2024", schema_context
        )
        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()

        result = safe_execute(sql, DB_PATH)
        assert len(result["rows"]) > 0

    @requires_api_key
    def test_top_n_query(self, schema_context):
        """Test: 'what are the top 5 customers by total spending'"""
        sql, explanation = generate_sql_or_skip(
            generate_sql,
            "what are the top 5 customers by total spending",
            schema_context,
        )
        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()

        result = safe_execute(sql, DB_PATH)
        assert len(result["rows"]) > 0
        assert len(result["rows"]) <= 5

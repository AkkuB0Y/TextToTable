"""
Safe SQL executor with self-healing retry — Phase 4.

Executes SQL against the SQLite database with safeguards:
- Read-only enforcement (only SELECT allowed)
- Row limit enforcement
- Retry with Claude-based SQL fixing on errors
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from pipeline.agent import fix_sql, get_schema_context

# ─── Configuration ──────────────────────────────────────────────────────────────

MAX_RETRIES = 3
MAX_ROWS = 500

# ─── Safety checks ──────────────────────────────────────────────────────────────

# Patterns that indicate non-SELECT statements
_DANGEROUS_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> None:
    """
    Validate that the SQL is safe to execute.

    Raises:
        ValueError: If the SQL contains dangerous statements.
    """
    stripped = sql.strip().rstrip(";").strip()

    if not stripped.upper().startswith("SELECT"):
        raise ValueError(
            f"Only SELECT statements are allowed. Got: {stripped[:50]}..."
        )

    if _DANGEROUS_PATTERNS.search(stripped):
        raise ValueError(
            "SQL contains forbidden keywords (INSERT/UPDATE/DELETE/DROP/etc.)"
        )


# ─── Public API ─────────────────────────────────────────────────────────────────


def safe_execute(sql: str, db_path: str | Path) -> dict:
    """
    Execute a SQL query safely with retry logic.

    If the SQL fails, uses Claude to fix it and retries (up to MAX_RETRIES).
    Enforces read-only queries and row limits.

    Args:
        sql: The SQL query to execute.
        db_path: Path to the SQLite database file.

    Returns:
        A dict with keys:
        - rows: list[dict] — the result rows
        - columns: list[str] — column names
        - sql: str — the SQL that was actually executed (may differ from input if fixed)
        - row_count: int — total rows returned
        - truncated: bool — whether results were truncated to MAX_ROWS

    Raises:
        ValueError: If SQL is not a SELECT statement.
        sqlite3.Error: If all retry attempts fail.
    """
    _validate_sql(sql)

    schema_context = get_schema_context(db_path)
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql)
            rows_raw = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            # Convert Row objects to dicts
            rows = [dict(r) for r in rows_raw]

            # Enforce row limit
            truncated = len(rows) > MAX_ROWS
            if truncated:
                rows = rows[:MAX_ROWS]

            return {
                "rows": rows,
                "columns": columns,
                "sql": sql,
                "row_count": len(rows),
                "truncated": truncated,
            }

        except sqlite3.Error as e:
            last_error = e
            print(
                f"⚠️  SQL execution failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
            )
            print(f"    SQL: {sql[:200]}")

            if attempt < MAX_RETRIES - 1:
                # Ask Claude to fix the SQL
                try:
                    fixed_sql, fix_explanation = fix_sql(sql, str(e), schema_context)
                    print(f"🔧  Claude fix attempt: {fix_explanation}")
                    _validate_sql(fixed_sql)  # Re-validate the fixed SQL
                    sql = fixed_sql
                except Exception as fix_error:
                    print(f"❌  Fix attempt failed: {fix_error}")
                    # Continue to next retry with the same SQL
        finally:
            conn.close()

    # All retries exhausted
    raise sqlite3.Error(
        f"Query failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )

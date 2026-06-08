"""
Claude SQL generation agent — Phase 4.

Converts natural-language queries into valid SQLite SELECT statements
using Claude as the reasoning engine. Includes self-healing: if the
generated SQL fails execution, the error is fed back to Claude for
a corrective attempt (up to MAX_FIX_ATTEMPTS).
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import anthropic

# ─── Configuration ──────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 600  # SQL rarely needs more
MAX_FIX_ATTEMPTS = 2

# ─── Schema loader (runs once at import / startup) ─────────────────────────────

_schema_context: str | None = None


def _load_schema_context(db_path: str | Path) -> str:
    """
    Build a schema context string for Claude containing:
    - CREATE TABLE statements (from sqlite_master)
    - 3 sample rows per table
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    parts: list[str] = []

    # Get all user tables
    tables = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    for table in tables:
        table_name = table["name"]
        create_sql = table["sql"]
        parts.append(f"-- Table: {table_name}")
        parts.append(create_sql + ";")
        parts.append("")

        # Sample rows
        sample_rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
        if sample_rows:
            cols = [desc[0] for desc in conn.execute(f"SELECT * FROM {table_name} LIMIT 1").description]
            parts.append(f"-- Sample data from {table_name}:")
            parts.append(f"-- Columns: {', '.join(cols)}")
            for row in sample_rows:
                parts.append(f"--   {dict(row)}")
            parts.append("")

        # Row count
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        parts.append(f"-- Total rows in {table_name}: {count}")
        parts.append("")

    conn.close()
    return "\n".join(parts)


def get_schema_context(db_path: str | Path) -> str:
    """Return cached schema context, building it on first call."""
    global _schema_context
    if _schema_context is None:
        _schema_context = _load_schema_context(db_path)
    return _schema_context


# ─── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a SQL generation assistant for a SQLite database.

You have access to the following database schema:

{schema}

Rules:
- Generate SELECT queries only. Never INSERT, UPDATE, DELETE, DROP, ALTER, or any DDL/DML.
- Always LIMIT results to 500 rows unless the user asks for a specific count.
- Use table aliases for clarity (e.g., o for orders, c for customers, p for products).
- For date/time filtering, the created_at column uses ISO 8601 format (e.g., '2024-01-01T00:00:00').
  Use strftime() or date() functions for date manipulation in SQLite.
- "Last quarter" means the most recent complete quarter. "Last month" means the previous calendar month.
  Use date('now') as the reference point.
- If the question is ambiguous about time, default to the last 30 days.
- For "revenue", use SUM(amount). For "order count", use COUNT(*).
- When grouping by region, include all regions even if some have zero.
- Output ONLY the SQL inside <sql> tags and a one-sentence explanation inside <explanation> tags.
- If the question cannot be answered with the available schema, output <sql>UNANSWERABLE</sql> and explain why in <explanation> tags.
"""

FIX_PROMPT = """The following SQL query failed with an error. Please fix it.

Original SQL:
```sql
{sql}
```

Error message:
{error}

Database schema:
{schema}

Rules:
- Generate only valid SQLite SELECT statements.
- Fix the specific error mentioned above.
- Output ONLY the corrected SQL inside <sql> tags and a brief explanation of what you fixed inside <explanation> tags.
"""


# ─── Tag extraction ─────────────────────────────────────────────────────────────

def extract_tag(text: str, tag: str) -> str:
    """
    Extract content between <tag>...</tag> from Claude's response.

    Args:
        text: The full response text from Claude.
        tag: The tag name (e.g., 'sql', 'explanation').

    Returns:
        The content between the tags, stripped of whitespace.
        Returns empty string if tag not found.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


# ─── Core API ───────────────────────────────────────────────────────────────────

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """Lazy-init the Anthropic client (uses ANTHROPIC_API_KEY env var)."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please set it before using the SQL generation agent."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def generate_sql(query: str, schema_context: str) -> tuple[str, str]:
    """
    Ask Claude to generate a SQL query from a natural-language question.

    Args:
        query: The cleaned natural-language question (from normalizer).
        schema_context: The database schema string (from get_schema_context).

    Returns:
        A tuple of (sql_string, explanation_string).
        sql_string will be 'UNANSWERABLE' if Claude can't map the question.

    Raises:
        RuntimeError: If the API key is not set or Claude returns no SQL.
    """
    client = _get_client()

    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT.format(schema=schema_context),
        messages=[{"role": "user", "content": query}],
    )

    text = resp.content[0].text
    sql = extract_tag(text, "sql")
    explanation = extract_tag(text, "explanation")

    if not sql:
        raise RuntimeError(
            f"Claude did not return SQL in the expected <sql> tags. "
            f"Raw response: {text[:500]}"
        )

    return sql, explanation


def fix_sql(sql: str, error: str, schema_context: str) -> tuple[str, str]:
    """
    Ask Claude to fix a broken SQL query given the error message.

    Args:
        sql: The SQL that failed.
        error: The error message from SQLite.
        schema_context: The database schema string.

    Returns:
        A tuple of (fixed_sql, explanation).
    """
    client = _get_client()

    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": FIX_PROMPT.format(
                    sql=sql, error=error, schema=schema_context,
                ),
            }
        ],
    )

    text = resp.content[0].text
    fixed_sql = extract_tag(text, "sql")
    explanation = extract_tag(text, "explanation")

    if not fixed_sql:
        # Fall back to returning the original if Claude can't extract
        return sql, f"Fix attempt failed: {text[:200]}"

    return fixed_sql, explanation

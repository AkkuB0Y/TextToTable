"""Shared pytest fixtures — loads backend/.env before any tests run."""

from pathlib import Path

import anthropic
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def generate_sql_or_skip(generate_sql, query: str, schema_ctx: str):
    """Call Claude; skip (not fail) on auth/billing issues."""
    try:
        return generate_sql(query, schema_ctx)
    except anthropic.AuthenticationError:
        pytest.skip("ANTHROPIC_API_KEY is invalid or rejected by Anthropic")
    except anthropic.BadRequestError as exc:
        message = str(exc).lower()
        if "credit balance" in message or "billing" in message:
            pytest.skip("Anthropic account has insufficient credits")
        raise

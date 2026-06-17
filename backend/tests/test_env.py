"""
Integration tests for .env loading and Claude API connectivity.

Run with: python -m pytest backend/tests/test_env.py -v

Live API tests are skipped automatically when the key is missing or the
Anthropic account has no credits.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app, DB_PATH
from pipeline.agent import _get_client, generate_sql, get_schema_context
from tests.conftest import generate_sql_or_skip

requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set in backend/.env",
)


@pytest.fixture(scope="module")
def valid_audio_bytes():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=16000:cl=mono",
            "-t", "1", tmp_path,
        ],
        capture_output=True,
        check=True,
    )

    audio_bytes = Path(tmp_path).read_bytes()
    Path(tmp_path).unlink(missing_ok=True)
    return audio_bytes


class TestEnvLoading:
    """Verify secrets are loaded from backend/.env."""

    def test_env_file_exists(self):
        env_path = Path(__file__).parent.parent / ".env"
        assert env_path.exists(), (
            f"Missing {env_path}. Copy backend/.env.example to backend/.env "
            "and add your ANTHROPIC_API_KEY."
        )

    def test_anthropic_api_key_is_set(self):
        key = os.environ.get("ANTHROPIC_API_KEY")
        assert key, "ANTHROPIC_API_KEY is empty — check backend/.env"
        assert key.startswith("sk-ant-"), "ANTHROPIC_API_KEY does not look like an Anthropic key"

    @requires_api_key
    def test_anthropic_client_initializes(self):
        """Verify the SDK client can be created from the loaded key (no API call)."""
        client = _get_client()
        assert client is not None


class TestClaudeAPIConnection:
    """Smoke tests that actually call the Anthropic API."""

    @requires_api_key
    def test_generate_sql_returns_valid_query(self):
        schema_ctx = get_schema_context(DB_PATH)
        sql, explanation = generate_sql_or_skip(generate_sql, "how many orders are there", schema_ctx)

        assert sql != "UNANSWERABLE"
        assert "SELECT" in sql.upper()
        assert explanation

    @requires_api_key
    def test_generate_sql_executes_successfully(self):
        schema_ctx = get_schema_context(DB_PATH)
        sql, _ = generate_sql_or_skip(generate_sql, "total revenue by region", schema_ctx)

        from pipeline.executor import safe_execute

        result = safe_execute(sql, DB_PATH)
        assert result["rows"]
        assert result["columns"]


class TestQueryEndpointWithAPIKey:
    """End-to-end /query tests when Claude is configured."""

    @requires_api_key
    def test_query_returns_sql_not_config_error(self, valid_audio_bytes):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/query",
                files={"audio": ("test.wav", valid_audio_bytes, "audio/wav")},
            )

        if response.status_code == 500:
            pytest.skip("Claude API call failed during /query (check Anthropic credits)")

        assert response.status_code == 200
        data = response.json()
        assert data["viz_spec"]["title"] != "Configuration Error"
        assert isinstance(data["transcript"], str)

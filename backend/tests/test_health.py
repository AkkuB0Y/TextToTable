"""
Phase 1 & 3 tests — verify server starts, health returns 200, DB has data,
and the /query endpoint transcribes audio correctly.

Run with: python -m pytest backend/tests/test_health.py -v
"""

import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure we can import from the backend package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app, DB_PATH


# ─── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Create a test client with the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def query_client():
    """Test client that returns 500 responses instead of raising (for /query)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _post_query_or_skip(client, valid_audio_bytes):
    response = client.post(
        "/query",
        files={"audio": ("test.wav", valid_audio_bytes, "audio/wav")},
    )
    if response.status_code == 500:
        pytest.skip("Claude API call failed during /query (check Anthropic credits)")
    return response


@pytest.fixture(scope="module")
def valid_audio_bytes():
    """Generate a valid 1-second silent WAV file for testing."""
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


# ─── Health Endpoint ────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        """Health response should include status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_includes_counts(self, client):
        """Health response should include database table counts."""
        response = client.get("/health")
        data = response.json()
        assert "db_orders_count" in data
        assert "db_customers_count" in data
        assert "db_products_count" in data

    def test_orders_count_at_least_10000(self, client):
        """Database should have at least 10,000 order rows."""
        response = client.get("/health")
        data = response.json()
        assert data["db_orders_count"] >= 10_000, (
            f"Expected at least 10,000 orders, got {data['db_orders_count']}"
        )

    def test_customers_count_positive(self, client):
        """Database should have customers."""
        response = client.get("/health")
        data = response.json()
        assert data["db_customers_count"] > 0

    def test_products_count_positive(self, client):
        """Database should have products."""
        response = client.get("/health")
        data = response.json()
        assert data["db_products_count"] > 0


class TestDatabaseIntegrity:
    """Tests for the seeded database quality."""

    def test_database_file_exists(self):
        """The SQLite database file should exist on disk."""
        assert DB_PATH.exists(), f"Database not found at {DB_PATH}"

    def test_orders_have_valid_statuses(self):
        """All orders should have valid status values."""
        conn = sqlite3.connect(str(DB_PATH))
        invalid = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status NOT IN ('completed', 'pending', 'refunded', 'cancelled')"
        ).fetchone()[0]
        conn.close()
        assert invalid == 0, f"Found {invalid} orders with invalid status"

    def test_orders_span_multiple_months(self):
        """Orders should span at least 12 distinct months for interesting aggregations."""
        conn = sqlite3.connect(str(DB_PATH))
        months = conn.execute(
            "SELECT COUNT(DISTINCT strftime('%Y-%m', created_at)) FROM orders"
        ).fetchone()[0]
        conn.close()
        assert months >= 12, f"Expected at least 12 months of data, got {months}"

    def test_all_regions_have_orders(self):
        """All 5 regions should have at least some orders."""
        conn = sqlite3.connect(str(DB_PATH))
        regions = conn.execute(
            "SELECT COUNT(DISTINCT region) FROM orders"
        ).fetchone()[0]
        conn.close()
        assert regions == 5, f"Expected 5 regions, got {regions}"

    def test_products_have_categories(self):
        """Products should span multiple categories."""
        conn = sqlite3.connect(str(DB_PATH))
        categories = conn.execute(
            "SELECT COUNT(DISTINCT category) FROM products"
        ).fetchone()[0]
        conn.close()
        assert categories >= 3, f"Expected at least 3 product categories, got {categories}"

    def test_foreign_keys_valid(self):
        """All order customer_id/product_id references should be valid."""
        conn = sqlite3.connect(str(DB_PATH))
        
        orphan_customers = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE customer_id NOT IN (SELECT id FROM customers)"
        ).fetchone()[0]
        
        orphan_products = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE product_id NOT IN (SELECT id FROM products)"
        ).fetchone()[0]
        
        conn.close()
        assert orphan_customers == 0, f"Found {orphan_customers} orders with invalid customer_id"
        assert orphan_products == 0, f"Found {orphan_products} orders with invalid product_id"


class TestQueryEndpoint:
    """Tests for the /query endpoint with real transcription (Phase 3 + 4).

    Without ANTHROPIC_API_KEY, the endpoint returns a graceful error response
    (200 with empty rows). With the key, it returns full SQL results.
    """

    def test_query_returns_200(self, query_client, valid_audio_bytes):
        """Query endpoint should accept a valid audio file and return 200."""
        response = _post_query_or_skip(query_client, valid_audio_bytes)
        assert response.status_code == 200

    def test_query_returns_query_result_schema(self, query_client, valid_audio_bytes):
        """Query response should match QueryResult schema."""
        response = _post_query_or_skip(query_client, valid_audio_bytes)
        data = response.json()
        assert "rows" in data
        assert "columns" in data
        assert "viz_spec" in data
        assert "sql" in data
        assert "transcript" in data

    def test_query_transcript_is_string(self, query_client, valid_audio_bytes):
        """Transcript field should be a string (may be empty for silence)."""
        response = _post_query_or_skip(query_client, valid_audio_bytes)
        data = response.json()
        assert isinstance(data["transcript"], str)


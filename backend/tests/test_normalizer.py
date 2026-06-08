"""Unit tests for the transcript normalizer (Phase 3)."""

import sys
from pathlib import Path

# Ensure backend/ is on the import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalizer import normalize


class TestNormalize:
    """Tests for normalize()."""

    def test_removes_fillers(self):
        raw = "uh show me, like, total revenue by region"
        assert normalize(raw) == "show me total revenue by region"

    def test_removes_multiple_fillers(self):
        raw = "Um, basically, show me the um top products, you know"
        result = normalize(raw)
        assert "um" not in result
        assert "basically" not in result
        assert "you know" not in result
        assert "show me" in result
        assert "top products" in result

    def test_lowercases(self):
        raw = "Show Me Revenue BY REGION"
        assert normalize(raw) == "show me revenue by region"

    def test_collapses_whitespace(self):
        raw = "show   me    revenue   by   region"
        assert normalize(raw) == "show me revenue by region"

    def test_strips_edges(self):
        raw = "  show me revenue  "
        assert normalize(raw) == "show me revenue"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_only_fillers(self):
        raw = "um uh like"
        result = normalize(raw)
        assert result == ""

    def test_preserves_meaningful_words(self):
        raw = "what is the total revenue for last quarter"
        assert normalize(raw) == "what is the total revenue for last quarter"

    def test_filler_at_start_and_end(self):
        raw = "So, show me revenue, basically"
        result = normalize(raw)
        assert "show me revenue" in result
        assert not result.startswith("so")
        assert not result.endswith("basically")

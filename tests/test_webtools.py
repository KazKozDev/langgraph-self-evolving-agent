"""Tests for web tools."""
from src.webtools import search, fetch


class TestWebSearch:
    def test_search_returns_results(self):
        results = search("Python programming language", max_results=3)
        assert isinstance(results, list)
        # May be empty in CI/offline, but should be a list
        for r in results:
            assert "title" in r
            assert "snippet" in r

    def test_fetch_url(self):
        text = fetch("https://example.com", timeout=10)
        assert isinstance(text, str)
        # Example.com has "Example Domain" somewhere
        assert len(text) > 0

    def test_fetch_invalid_url(self):
        text = fetch("https://this-does-not-exist-12345.com", timeout=5)
        assert text.startswith("[fetch error")

"""Tests for domain-specific executors."""

import sys
from types import ModuleType

import pytest

from src.domain_executors import ResearchExecutor


@pytest.mark.parametrize(
    ("goal", "expected_lang"),
    [
        ("latest AI research 🚀", "en"),
        ("последние исследования ИИ", "ru"),
    ],
)
def test_rag_search_builds_context_with_detected_language(monkeypatch, goal, expected_lang):
    module = ModuleType("production_rag_pipeline")
    calls = {}

    def search_extract_rerank(*, query, lang):
        calls.update(query=query, lang=lang)
        return ["chunk"], [{"url": "https://example.com"}], ["https://example.com"]

    def build_llm_context(chunks, results, *, fetched_urls):
        calls.update(chunks=chunks, results=results, fetched_urls=fetched_urls)
        return "source context", 1, 1

    module.search_extract_rerank = search_extract_rerank
    module.build_llm_context = build_llm_context
    monkeypatch.setitem(sys.modules, "production_rag_pipeline", module)

    context = ResearchExecutor()._rag_search(goal)

    assert context == "source context"
    assert calls == {
        "query": goal,
        "lang": expected_lang,
        "chunks": ["chunk"],
        "results": [{"url": "https://example.com"}],
        "fetched_urls": ["https://example.com"],
    }


def test_rag_search_returns_empty_context_on_pipeline_failure(monkeypatch):
    module = ModuleType("production_rag_pipeline")

    def search_extract_rerank(**_kwargs):
        raise RuntimeError("search unavailable")

    module.search_extract_rerank = search_extract_rerank
    module.build_llm_context = lambda *_args, **_kwargs: ("unused", 0, 0)
    monkeypatch.setitem(sys.modules, "production_rag_pipeline", module)

    assert ResearchExecutor()._rag_search("query") == ""

"""Tests for automatic domain detection."""
import os

os.environ["EVOLUTION_MOCK"] = "true"

from src.domain_classifier import VALID_DOMAINS, classify_domain


class TestClassifier:
    def test_research_goal(self):
        assert classify_domain("Find and compare vector databases for RAG") == "research"

    def test_writing_goal(self):
        assert classify_domain("Write a README for my FastAPI project") == "writing"

    def test_planning_goal(self):
        assert classify_domain("Make a roadmap to migrate the monolith") == "planning"

    def test_coding_goal_default(self):
        assert classify_domain("Implement a prime number checker with tests") == "coding"

    def test_empty_returns_default(self):
        assert classify_domain("", default="general") == "general"

    def test_always_valid_domain(self):
        for goal in ["build an api", "research llms", "write a blog", "plan a sprint"]:
            assert classify_domain(goal) in VALID_DOMAINS

"""Tests for GitHub exporter."""
import os
import sys
import tempfile

os.environ["EVOLUTION_MOCK"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.github_exporter import GitHubExporter


class TestGitHubExporter:
    def test_ensure_repo_creates_git(self):
        with tempfile.TemporaryDirectory() as td:
            exporter = GitHubExporter(repo_path=td, auto_push=False)
            assert exporter._ensure_repo()
            assert os.path.isdir(f"{td}/.git")

    def test_export_skill_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            exporter = GitHubExporter(repo_path=td, auto_push=False)
            exporter._ensure_repo()
            skill = {
                "name": "test-skill",
                "domain": "debugging",
                "triggers": ["when error"],
                "steps": ["step 1", "step 2"],
                "pitfalls": ["pitfall 1"],
                "success_rate": 0.9,
            }
            result = exporter.export_skill(skill)
            assert result  # Git commit succeeded
            assert os.path.isfile(f"{td}/skills/test-skill.md")

    def test_safe_filename(self):
        exporter = GitHubExporter(repo_path="/tmp", auto_push=False)
        assert exporter._safe_filename("Hello World/Test") == "hello-world-test"
        assert exporter._safe_filename("A" * 100) == "a" * 64

    def test_skill_to_md(self):
        exporter = GitHubExporter(repo_path="/tmp", auto_push=False)
        skill = {"name": "debug-py", "steps": ["log", "check"], "triggers": ["500 error"]}
        md = exporter._skill_to_md(skill)
        assert "# debug-py" in md
        assert "## Steps" in md
        assert "- 500 error" in md

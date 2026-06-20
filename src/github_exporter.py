"""
GitHub Exporter — auto-commit and push evolved skills to a GitHub repo.

Uses git CLI (no external deps). Configure via env vars:
  GITHUB_REPO_PATH — local clone of the target repo (default: ~/.self-evolving-agent/repo)
  GITHUB_SKILLS_DIR — subdirectory for skill files (default: skills/)
  GITHUB_AUTO_PUSH — whether to push after commit (default: true)
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path


class GitHubExporter:
    """Exports skills as Markdown files to a Git repo and commits/pushes them."""

    def __init__(
        self,
        repo_path: str | None = None,
        skills_dir: str = "skills",
        auto_push: bool = True,
    ):
        self.repo_path = Path(os.path.expanduser(
            repo_path or os.getenv("GITHUB_REPO_PATH", "~/.self-evolving-agent/repo")
        ))
        self.skills_dir = skills_dir
        self.auto_push = auto_push

    # ── Public API ────────────────────────────────────────────

    def export_skill(self, skill: dict) -> bool:
        """Export one skill as a Markdown file and commit it.

        Returns True if committed successfully.
        """
        if not self._ensure_repo():
            return False

        # Write skill as .md file
        name = self._safe_filename(skill.get("name", "unnamed"))
        content = self._skill_to_md(skill)
        filepath = self.repo_path / self.skills_dir / f"{name}.md"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)

        # Git add + commit
        return self._git_add_commit(filepath, f"skill: {name}")

    def export_all(self, skills: list[dict]) -> dict:
        """Export multiple skills. Returns {exported: N, failed: N}."""
        exported = 0
        failed = 0
        for sk in skills:
            if self.export_skill(sk):
                exported += 1
            else:
                failed += 1
        if exported > 0 and self.auto_push:
            self._git_push()
        return {"exported": exported, "failed": failed}

    def push(self) -> bool:
        """Push commits to remote."""
        return self._git_push()

    # ── Internal ──────────────────────────────────────────────

    def _ensure_repo(self) -> bool:
        """Ensure the repo directory exists and is a git repo."""
        if not self.repo_path.exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            return self._run(["git", "init"], cwd=self.repo_path)
        return True

    def _safe_filename(self, name: str) -> str:
        """Convert skill name to a safe filename."""
        return name.lower().replace(" ", "-").replace("/", "-")[:64]

    def _skill_to_md(self, skill: dict) -> str:
        """Convert a skill dict to Markdown."""
        parts = [
            f"# {skill.get('name', 'Untitled')}",
            "",
            f"**Domain:** {skill.get('domain', 'unknown')}",
            f"**Success rate:** {skill.get('success_rate', 1.0)}",
            f"**Created:** {datetime.now().isoformat()}",
            "",
        ]
        triggers = skill.get("triggers", [])
        if triggers:
            parts.append("## When to use")
            for t in triggers:
                parts.append(f"- {t}")
            parts.append("")

        steps = skill.get("steps", [])
        if steps:
            parts.append("## Steps")
            for i, s in enumerate(steps, 1):
                parts.append(f"{i}. {s}")
            parts.append("")

        pitfalls = skill.get("pitfalls", [])
        if pitfalls:
            parts.append("## Pitfalls")
            for p in pitfalls:
                parts.append(f"- ⚠️ {p}")
            parts.append("")

        return "\n".join(parts)

    def _git_add_commit(self, filepath: Path, message: str) -> bool:
        """Stage and commit a file."""
        rel = filepath.relative_to(self.repo_path)
        if not self._run(["git", "add", str(rel)], cwd=self.repo_path):
            return False
        return self._run(["git", "commit", "-m", message, "--allow-empty"], cwd=self.repo_path)

    def _git_push(self) -> bool:
        """Push to origin/main."""
        return self._run(["git", "push", "origin", "main"], cwd=self.repo_path)

    def _run(self, cmd: list[str], cwd: Path) -> bool:
        try:
            subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=30)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "setup-brand-ugc" / "scripts" / "setup_check.py"
START = "<!-- brand-ugc:start -->"
END = "<!-- brand-ugc:end -->"


def _run(project_root: Path, home: Path, *extra: str) -> dict:
    env = dict(os.environ)
    env["HOME"] = str(home)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "agents-doc",
            "--project-root",
            str(project_root),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class AgentsDocTests(unittest.TestCase):
    def test_creates_both_docs_when_neither_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()

            report = _run(project_root, home)
            agents = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (project_root / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertEqual(report["agents_md"]["action"], "created")
        self.assertEqual(report["claude_md"]["action"], "created")
        self.assertTrue(report["agents_md"]["written"])
        self.assertTrue(report["claude_md"]["written"])

        self.assertIn("## brand-ugc", agents)
        self.assertIn("$ask-brand", agents)
        self.assertIn(".brand_ugc/brands/<brand>/profile.json", agents)
        self.assertIn(".brand_ugc/credentials.json", agents)
        self.assertTrue(agents.endswith(END + "\n"))

        self.assertIn("@AGENTS.md", claude)
        self.assertNotIn("$ask-brand", claude)

    def test_adds_pointer_to_existing_claude_md_without_duplicating_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()
            (project_root / "CLAUDE.md").write_text(
                "# 项目说明\n\n用户自己写的内容。\n", encoding="utf-8"
            )

            _run(project_root, home)
            agents = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (project_root / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertIn("用户自己写的内容。", claude)
        self.assertIn("@AGENTS.md", claude)
        self.assertNotIn("$ask-brand", claude)
        self.assertIn("$ask-brand", agents)

    def test_is_idempotent_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()
            (project_root / "AGENTS.md").write_text(
                "# 项目说明\n\n用户自己写的内容。\n", encoding="utf-8"
            )

            first = _run(project_root, home)
            after_first = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            second = _run(project_root, home)
            after_second = (project_root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (project_root / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertEqual(first["agents_md"]["action"], "updated")
        self.assertEqual(second["agents_md"]["action"], "unchanged")
        self.assertEqual(second["claude_md"]["action"], "unchanged")
        self.assertFalse(second["agents_md"]["written"])
        self.assertEqual(after_first, after_second)
        self.assertIn("用户自己写的内容。", after_second)
        self.assertEqual(after_second.count(START), 1)
        self.assertEqual(after_second.count(END), 1)
        self.assertEqual(claude.count(START), 1)

    def test_replaces_stale_block_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()
            (project_root / "AGENTS.md").write_text(
                f"# 头部\n\n{START}\n旧的引导\n{END}\n\n## 尾部\n",
                encoding="utf-8",
            )

            report = _run(project_root, home)
            agents = (project_root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertEqual(report["agents_md"]["action"], "updated")
        self.assertNotIn("旧的引导", agents)
        self.assertIn("## brand-ugc", agents)
        self.assertTrue(agents.startswith("# 头部\n"))
        self.assertTrue(agents.endswith("\n## 尾部\n"))

    def test_replaces_guidance_previously_written_into_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()
            (project_root / "CLAUDE.md").write_text(
                f"{START}\n## brand-ugc\n\n统一入口是 `$ask-brand`。\n{END}\n",
                encoding="utf-8",
            )

            _run(project_root, home)
            claude = (project_root / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertNotIn("$ask-brand", claude)
        self.assertIn("@AGENTS.md", claude)
        self.assertEqual(claude.count(START), 1)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()

            report = _run(project_root, home, "--dry-run")

            self.assertTrue(report["dry_run"])
            self.assertEqual(report["agents_md"]["action"], "created")
            self.assertFalse(report["agents_md"]["written"])
            self.assertFalse(report["claude_md"]["written"])
            self.assertFalse((project_root / "AGENTS.md").exists())
            self.assertFalse((project_root / "CLAUDE.md").exists())

    def test_block_lists_existing_brand_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            profile = project_root / ".brand_ugc" / "brands" / "acme" / "profile.json"
            profile.parent.mkdir(parents=True)
            profile.write_text("{}", encoding="utf-8")

            report = _run(project_root, home)

        self.assertIn("当前：`acme`", report["block"])


if __name__ == "__main__":
    unittest.main()

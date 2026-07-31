from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Pinned so the check is deterministic; bump deliberately and re-verify by hand.
SKILLS_PACKAGE = "skills@1.5.19"

SKILL_NAMES = [
    "ask-brand",
    "brand-profile",
    "image-generator",
    "setup-brand-ugc",
    "ugc-image-post",
    "ugc-storyboard",
    "xhs-topic-radar",
]

# Project-scope install target per agent, from the `skills` CLI's own agent registry.
AGENT_PROJECT_DIRS = {
    "codex": ".agents/skills",
    "claude-code": ".claude/skills",
    "pi": ".pi/skills",
}


def _npx_available() -> bool:
    return shutil.which("npx") is not None


@unittest.skipUnless(_npx_available(), "npx is not available in this environment")
class SkillAgentNeutralityTests(unittest.TestCase):
    """ADR 0004: SKILL.md must install identically across every supported agent."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source_dir = tempfile.mkdtemp(prefix="brand-ugc-skills-source-")
        for name in SKILL_NAMES:
            shutil.copytree(ROOT / name, Path(cls.source_dir) / name)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.source_dir, ignore_errors=True)

    def _install(self, agent: str) -> Path:
        workdir = tempfile.mkdtemp(prefix=f"brand-ugc-skills-{agent}-")
        self.addCleanup(shutil.rmtree, workdir, ignore_errors=True)
        result = subprocess.run(
            [
                "npx",
                "-y",
                SKILLS_PACKAGE,
                "add",
                self.source_dir,
                "--agent",
                agent,
                "--skill",
                "*",
                "--yes",
            ],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(workdir) / AGENT_PROJECT_DIRS[agent]

    def test_skill_md_is_byte_identical_across_agents(self) -> None:
        for agent in AGENT_PROJECT_DIRS:
            with self.subTest(agent=agent):
                installed_root = self._install(agent)
                for name in SKILL_NAMES:
                    source_skill_md = (Path(self.source_dir) / name / "SKILL.md").read_bytes()
                    installed_skill_md = (installed_root / name / "SKILL.md").read_bytes()
                    self.assertEqual(
                        source_skill_md,
                        installed_skill_md,
                        f"{name} SKILL.md diverged when installed for agent={agent}; "
                        "see docs/adr/0004-skills-are-agent-neutral.md",
                    )

    def test_only_display_metadata_is_agent_specific(self) -> None:
        """Per ADR 0004, agents/<agent-name>.yaml is the only allowed per-agent file."""
        for name in SKILL_NAMES:
            agents_dir = ROOT / name / "agents"
            if not agents_dir.is_dir():
                continue
            for path in agents_dir.iterdir():
                self.assertTrue(
                    path.is_file() and path.suffix == ".yaml",
                    f"Unexpected agent-specific artifact: {path}",
                )


if __name__ == "__main__":
    unittest.main()

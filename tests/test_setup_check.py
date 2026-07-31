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


def _isolated_env(home: Path, **extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("XDG_CONFIG_HOME", None)
    env.pop("EVOLINK_API_KEY", None)
    env.pop("IMAGEGEN_API_KEY", None)
    env.pop("TIKHUB_API_KEY", None)
    env.update(extra)
    return env


class SetupCheckTests(unittest.TestCase):
    def test_check_reports_expected_top_level_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "check", "--project-root", tmp],
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        for key in (
            "python",
            "node",
            "imagemagick",
            "cjk_font",
            "ffmpeg",
            "ffprobe",
            "skills",
            "credentials",
            "brand_profiles",
        ):
            self.assertIn(key, report)
        self.assertEqual(
            set(report["skills"]),
            {
                "ask-brand",
                "xhs-topic-radar",
                "brand-profile",
                "ugc-image-post",
                "ugc-storyboard",
                "image-generator",
            },
        )
        self.assertTrue(report["python"]["found"])
        self.assertEqual(report["brand_profiles"], [])
        # evolink.configured also reflects an in-repo local-edit-mode install
        # (image-generator/secrets/api_key.txt), so only assert the shape here;
        # the environment-variable path is asserted precisely below.
        self.assertIsInstance(report["credentials"]["evolink"]["configured"], bool)
        self.assertFalse(report["credentials"]["tikhub"]["configured"])

    def test_check_detects_evolink_key_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "check", "--project-root", tmp],
                capture_output=True,
                text=True,
                env=_isolated_env(home, EVOLINK_API_KEY="sk-test-evolink"),
                check=False,
            )

        report = json.loads(result.stdout)
        self.assertTrue(report["credentials"]["evolink"]["configured"])
        self.assertEqual(report["credentials"]["evolink"]["source"], "environment")

    def test_check_detects_tikhub_key_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "check", "--project-root", tmp],
                capture_output=True,
                text=True,
                env=_isolated_env(home, TIKHUB_API_KEY="0123456789abcdef"),
                check=False,
            )

        report = json.loads(result.stdout)
        self.assertTrue(report["credentials"]["tikhub"]["configured"])
        self.assertEqual(report["credentials"]["tikhub"]["source"], "environment")

    def test_check_lists_existing_brand_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            brand_dir = project_root / ".brand_ugc" / "brands" / "acme"
            brand_dir.mkdir(parents=True)
            (brand_dir / "profile.json").write_text("{}", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "check", "--project-root", str(project_root)],
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )

        report = json.loads(result.stdout)
        self.assertEqual(report["brand_profiles"], ["acme"])

    def test_set_evolink_key_writes_to_global_skills_root_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".agents" / "skills" / "image-generator").mkdir(parents=True)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "set-evolink-key"],
                input="sk-test-key-1234\n",
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            secret_file = (
                home / ".agents" / "skills" / "image-generator" / "secrets" / "api_key.txt"
            )
            self.assertTrue(secret_file.is_file())
            self.assertEqual(secret_file.read_text(encoding="utf-8").strip(), "sk-test-key-1234")
            if os.name != "nt":
                self.assertEqual(oct(secret_file.stat().st_mode)[-3:], "600")

    def test_set_evolink_key_rejects_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".agents" / "skills" / "image-generator").mkdir(parents=True)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "set-evolink-key"],
                input="sk with space\n",
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("空格", result.stderr)


if __name__ == "__main__":
    unittest.main()

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
            "credentials_file",
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

    def test_init_creates_protected_project_credentials_and_check_reads_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            project_root.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "init",
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            initialized = json.loads(result.stdout)
            credentials_file = project_root / ".brand_ugc" / "credentials.json"
            self.assertEqual(
                Path(initialized["credentials_file"]).resolve(),
                credentials_file.resolve(),
            )
            self.assertTrue(initialized["created"])
            self.assertEqual(
                json.loads(credentials_file.read_text(encoding="utf-8")),
                {
                    "schemaVersion": 1,
                    "tikhubApiKey": "",
                    "evolinkApiKey": "",
                },
            )
            if os.name != "nt":
                self.assertEqual(oct(credentials_file.stat().st_mode)[-3:], "600")
            self.assertIn(
                ".brand_ugc/credentials.json",
                (project_root / ".gitignore").read_text(encoding="utf-8"),
            )

            credentials_file.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "tikhubApiKey": "project-tikhub-key",
                        "evolinkApiKey": "project-evolink-key",
                    }
                ),
                encoding="utf-8",
            )
            check = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "check",
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )

        self.assertEqual(check.returncode, 0, check.stderr)
        report = json.loads(check.stdout)
        self.assertTrue(report["credentials"]["tikhub"]["configured"])
        self.assertEqual(report["credentials"]["tikhub"]["source"], "project-file")
        self.assertTrue(report["credentials"]["evolink"]["configured"])
        self.assertEqual(report["credentials"]["evolink"]["source"], "project-file")

    def test_init_does_not_overwrite_existing_project_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            project_root = home / "project"
            credentials_file = project_root / ".brand_ugc" / "credentials.json"
            credentials_file.parent.mkdir(parents=True)
            credentials_file.write_text(
                '{"schemaVersion": 1, "tikhubApiKey": "keep-existing"}\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "init",
                    "--project-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
                env=_isolated_env(home),
                check=False,
            )
            preserved = credentials_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["created"])
        self.assertIn("keep-existing", preserved)

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

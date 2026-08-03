from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
IMAGEGEN = ROOT / "image-generator" / "scripts" / "generate_image.py"
sys.path.insert(0, str(IMAGEGEN.parent))

from generate_image import load_key  # noqa: E402


class ImagegenCompatibilityTests(unittest.TestCase):
    def test_load_key_reads_project_credentials_without_an_environment_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            credentials = project_root / ".brand_ugc" / "credentials.json"
            credentials.parent.mkdir()
            credentials.write_text(
                json.dumps({"schemaVersion": 1, "evolinkApiKey": "project-key"}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_key(None, project_root), "project-key")

    def test_nanobanana_dry_run_uses_evolink_async_image_contract(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(IMAGEGEN),
                "--provider",
                "nanobanana",
                "--prompt",
                "生成十二宫格产品分镜",
                "--aspect-ratio",
                "9:16",
                "--resolution",
                "2K",
                "--dry-run",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)

        self.assertEqual(payload["model"], "gemini-3-pro-image-preview")
        self.assertEqual(payload["size"], "9:16")
        self.assertEqual(payload["quality"], "2K")
        self.assertNotIn("messages", payload)
        self.assertNotIn("nbp_pic", proc.stdout)
        self.assertNotIn("8ai", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()

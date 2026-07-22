from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGEGEN = ROOT / "imagegen-api" / "scripts" / "generate_image.py"


class ImagegenCompatibilityTests(unittest.TestCase):
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

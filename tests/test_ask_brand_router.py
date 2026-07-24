from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "ask-brand" / "scripts" / "route_request.py"


class AskBrandRouterTests(unittest.TestCase):
    def test_explicit_image_post_request_routes_without_an_extra_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.png"
            product = root / "product.png"
            copy_file = root / "copy.txt"
            reference.write_bytes(b"reference")
            product.write_bytes(b"product")
            copy_file.write_text("对标文案", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROUTER),
                    "--request",
                    "根据这些对标图片和文案生成一篇小红书图文笔记",
                    "--reference-image",
                    str(reference),
                    "--reference-copy-file",
                    str(copy_file),
                    "--product-image",
                    str(product),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "ready")
        self.assertEqual(decision["recommended_skill"], "ugc-image-post")
        self.assertEqual(decision["missing_inputs"], [])
        self.assertEqual(decision["question"], "")

    def test_ambiguous_request_with_both_asset_sets_asks_one_routing_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                name: root / name
                for name in ("reference.png", "reference.mp4", "product.png", "copy.txt")
            }
            for path in paths.values():
                path.write_bytes(b"fixture")

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROUTER),
                    "--request",
                    "帮这个新品做营销内容",
                    "--reference-image",
                    str(paths["reference.png"]),
                    "--reference-copy-file",
                    str(paths["copy.txt"]),
                    "--reference-video",
                    str(paths["reference.mp4"]),
                    "--product-image",
                    str(paths["product.png"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "needs_confirmation")
        self.assertEqual(decision["recommended_skill"], "ugc-image-post")
        self.assertEqual(decision["question"].count("？"), 1)

    def test_explicit_image_request_reports_only_missing_required_inputs(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROUTER),
                "--request",
                "生成小红书图文",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(
            decision["missing_inputs"],
            ["对标图片", "对标文案", "产品图"],
        )
        self.assertEqual(decision["recommended_skill"], "ugc-image-post")


if __name__ == "__main__":
    unittest.main()

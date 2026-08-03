from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "ask-brand" / "scripts" / "route_request.py"
ROUTE_SCHEMA = ROOT / "ask-brand" / "schemas" / "route-decision.schema.json"


class AskBrandRouterTests(unittest.TestCase):
    def test_route_schema_allows_the_topic_radar_skill(self) -> None:
        schema = json.loads(ROUTE_SCHEMA.read_text(encoding="utf-8"))
        allowed = schema["properties"]["recommended_skill"]["enum"]
        self.assertIn("xhs-topic-radar", allowed)

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

    def test_daily_topic_request_routes_to_topic_radar(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROUTER),
                "--request",
                "请执行小红书每日选题生成",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "ready")
        self.assertEqual(decision["intent"], "topic_research")
        self.assertEqual(decision["recommended_skill"], "xhs-topic-radar")
        self.assertEqual(decision["question"], "")

    def test_generic_industry_topic_request_routes_to_topic_radar(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROUTER),
                "--request",
                "我需要软著的选题",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "ready")
        self.assertEqual(decision["intent"], "topic_research")
        self.assertEqual(decision["recommended_skill"], "xhs-topic-radar")
        self.assertEqual(decision["question"], "")

    def test_generic_xiaohongshu_production_still_routes_to_image_post(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROUTER),
                "--request",
                "根据这些素材生成小红书图文笔记",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["recommended_skill"], "ugc-image-post")
        self.assertEqual(decision["status"], "needs_input")

    def test_mixed_topic_and_production_request_asks_one_sequence_question(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROUTER),
                "--request",
                "先做选题研究再生成图文",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["status"], "needs_confirmation")
        self.assertEqual(decision["recommended_skill"], "xhs-topic-radar")
        self.assertEqual(decision["question"].count("？"), 1)


if __name__ == "__main__":
    unittest.main()

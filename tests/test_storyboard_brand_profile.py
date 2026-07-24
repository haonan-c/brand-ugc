from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "ugc-storyboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_public_pipeline import build_product_context, resolve_brand_profile  # noqa: E402


class StoryboardBrandProfileTests(unittest.TestCase):
    def test_selected_brand_product_is_added_below_task_specific_information(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile_file = Path(tmp) / "profile.json"
            profile_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "brand_id": "north-star",
                        "brand_name": "North Star",
                        "voice": {
                            "traits": ["克制", "可信"],
                            "prohibited_terms": ["绝对有效"],
                        },
                        "visual": {"colors": ["#17324D"]},
                        "compliance": {"prohibited_claims": ["七天见效"]},
                        "products": [
                            {
                                "product_id": "serum",
                                "name": "Daily Serum",
                                "verified_claims": [
                                    {
                                        "claim": "包装容量为30毫升",
                                        "evidence": "包装正面",
                                    }
                                ],
                            },
                            {
                                "product_id": "cream",
                                "name": "Daily Cream",
                                "verified_claims": [],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            context = resolve_brand_profile(profile_file, "serum")
            merged = build_product_context("本次任务：主打晨间使用。", context)

        self.assertEqual(context["product"]["product_id"], "serum")
        self.assertIn("本次任务：主打晨间使用。", merged)
        self.assertIn("North Star", merged)
        self.assertIn("包装容量为30毫升", merged)
        self.assertIn("七天见效", merged)
        self.assertLess(
            merged.index("本次任务：主打晨间使用。"),
            merged.index("North Star"),
        )

    def test_no_brand_profile_preserves_the_original_product_context_exactly(self) -> None:
        self.assertEqual(
            build_product_context("仅使用本次产品信息。", None),
            "仅使用本次产品信息。",
        )


if __name__ == "__main__":
    unittest.main()

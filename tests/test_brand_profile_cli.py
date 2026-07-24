from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "brand-profile" / "scripts" / "manage_profile.py"


def _profile() -> dict:
    return {
        "schema_version": 1,
        "brand_id": "north-star",
        "brand_name": "North Star",
        "audiences": ["都市通勤人群"],
        "voice": {
            "traits": ["克制", "可信"],
            "preferred_terms": ["日常护理"],
            "prohibited_terms": ["绝对有效"],
        },
        "visual": {
            "colors": ["#17324D", "#F5F1E8"],
            "fonts": [],
            "corner_radius": "medium",
        },
        "compliance": {"prohibited_claims": ["七天见效"]},
        "defaults": {"ctas": ["收藏备用"], "hashtags": ["#日常护理"]},
        "products": [
            {
                "product_id": "daily-serum",
                "name": "Daily Serum",
                "images": ["/tmp/daily-serum.png"],
                "verified_claims": [
                    {
                        "claim": "包装容量为30毫升",
                        "evidence": "用户提供的产品包装正面",
                    }
                ],
                "target_audiences": ["都市通勤人群"],
                "use_cases": ["晨间护理"],
                "prohibited_expressions": ["医学级修复"],
            }
        ],
    }


class BrandProfileCliTests(unittest.TestCase):
    def test_saved_profile_can_be_read_through_the_public_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_file = root / "profile.json"
            profile_file.write_text(
                json.dumps(_profile(), ensure_ascii=False),
                encoding="utf-8",
            )
            output_root = root / ".brand_ugc"

            saved = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "save",
                    "--profile-file",
                    str(profile_file),
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            shown = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "show",
                    "--brand-id",
                    "north-star",
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout), _profile())

    def test_task_overrides_are_resolved_without_rewriting_the_saved_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / ".brand_ugc"
            profile_file = root / "profile.json"
            profile_file.write_text(
                json.dumps(_profile(), ensure_ascii=False),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "save",
                    "--profile-file",
                    str(profile_file),
                    "--output-root",
                    str(output_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            overrides_file = root / "overrides.json"
            overrides_file.write_text(
                json.dumps(
                    {
                        "voice": {"traits": ["温暖", "可信"]},
                        "product": {"use_cases": ["晚间护理"]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            resolved = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "resolve",
                    "--brand-id",
                    "north-star",
                    "--product-id",
                    "daily-serum",
                    "--overrides-file",
                    str(overrides_file),
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            shown = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "show",
                    "--brand-id",
                    "north-star",
                    "--output-root",
                    str(output_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        effective = json.loads(resolved.stdout)
        self.assertEqual(effective["voice"]["traits"], ["温暖", "可信"])
        self.assertEqual(effective["product"]["use_cases"], ["晚间护理"])
        self.assertEqual(json.loads(shown.stdout), _profile())

    def test_unverified_product_claim_is_rejected_before_profile_is_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid = _profile()
            invalid["products"][0]["verified_claims"] = [
                {"claim": "七天改善全部皮肤问题"}
            ]
            profile_file = root / "profile.json"
            profile_file.write_text(
                json.dumps(invalid, ensure_ascii=False),
                encoding="utf-8",
            )
            output_root = root / ".brand_ugc"

            saved = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "save",
                    "--profile-file",
                    str(profile_file),
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(saved.returncode, 2)
        self.assertIn("evidence", saved.stderr)
        self.assertFalse(
            (output_root / "brands" / "north-star" / "profile.json").exists()
        )


if __name__ == "__main__":
    unittest.main()

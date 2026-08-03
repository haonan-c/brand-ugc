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
        "products": [
            {"product_id": "daily-serum", "name": "Daily Serum"},
            {"product_id": "night-cream", "name": "Night Cream"},
        ],
    }


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *argv],
        check=False,
        capture_output=True,
        text=True,
    )


class BrandInsightsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.output_root = self.root / ".brand_ugc"
        profile_file = self.root / "profile.json"
        profile_file.write_text(
            json.dumps(_profile(), ensure_ascii=False), encoding="utf-8"
        )
        saved = _run(
            "save",
            "--profile-file",
            str(profile_file),
            "--output-root",
            str(self.output_root),
        )
        self.assertEqual(saved.returncode, 0, saved.stderr)

    def _merge(self, patch: dict, name: str = "patch.json") -> subprocess.CompletedProcess:
        patch_file = self.root / name
        patch_file.write_text(json.dumps(patch, ensure_ascii=False), encoding="utf-8")
        return _run(
            "insights-merge",
            "--brand-id",
            "north-star",
            "--patch-file",
            str(patch_file),
            "--output-root",
            str(self.output_root),
        )

    def test_repeated_observation_from_a_second_source_raises_confidence(self) -> None:
        interview = self._merge(
            {
                "brand_id": "north-star",
                "source": "interview",
                "observed_at": "2026-07-20",
                "audience_insights": [
                    {
                        "audience": "熬夜加班的25-30岁女性",
                        "pain_points": ["第二天全脸暗沉"],
                    }
                ],
            },
            "interview.json",
        )
        radar = self._merge(
            {
                "brand_id": "north-star",
                "source": "platform_radar",
                "observed_at": "2026-08-03",
                "ref": {"run_id": "run-01", "note_urls": ["https://example.com/n/1"]},
                "audience_insights": [
                    {
                        "audience": "熬夜加班的25-30岁女性",
                        "pain_points": ["第二天全脸暗沉", "底妆卡粉"],
                        "native_phrases": ["回血"],
                    }
                ],
            },
            "radar.json",
        )

        self.assertEqual(interview.returncode, 0, interview.stderr)
        self.assertEqual(radar.returncode, 0, radar.stderr)

        entry = json.loads(radar.stdout)["audience_insights"][0]
        self.assertEqual(entry["pain_points"], ["第二天全脸暗沉", "底妆卡粉"])
        self.assertEqual(entry["native_phrases"], ["回血"])
        provenance = entry["provenance"]
        self.assertEqual(provenance["sources"], ["interview", "platform_radar"])
        self.assertEqual(provenance["observed_count"], 2)
        self.assertEqual(provenance["first_seen"], "2026-07-20")
        self.assertEqual(provenance["last_seen"], "2026-08-03")
        self.assertEqual(provenance["confidence"], "medium")
        self.assertEqual(provenance["observations"], [
            {"source": "interview", "observed_at": "2026-07-20"},
            {
                "source": "platform_radar",
                "observed_at": "2026-08-03",
                "ref": {"run_id": "run-01", "note_urls": ["https://example.com/n/1"]},
            },
        ])

    def test_merging_the_same_patch_twice_does_not_raise_confidence(self) -> None:
        patch = {
            "brand_id": "north-star",
            "source": "interview",
            "observed_at": "2026-08-03",
            "audience_insights": [
                {
                    "audience": "熬夜加班的25-30岁女性",
                    "pain_points": ["第二天全脸暗沉"],
                }
            ],
        }
        first = self._merge(patch, "again.json")
        second = self._merge(patch, "again.json")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        provenance = json.loads(second.stdout)["audience_insights"][0]["provenance"]
        self.assertEqual(provenance["observed_count"], 1)
        self.assertEqual(provenance["confidence"], "low")
        self.assertEqual(
            provenance["observations"],
            [{"source": "interview", "observed_at": "2026-08-03"}],
        )

    def test_same_day_source_counts_twice_when_refs_differ(self) -> None:
        for run_id in ("run-01", "run-02"):
            merged = self._merge(
                {
                    "brand_id": "north-star",
                    "source": "platform_radar",
                    "observed_at": "2026-08-03",
                    "ref": {"run_id": run_id},
                    "audience_insights": [{"audience": "通勤人群"}],
                },
                f"{run_id}.json",
            )
            self.assertEqual(merged.returncode, 0, merged.stderr)

        provenance = json.loads(merged.stdout)["audience_insights"][0]["provenance"]
        self.assertEqual(provenance["observed_count"], 2)
        self.assertEqual(provenance["confidence"], "medium")

    def test_three_observations_across_two_sources_reach_high_confidence(self) -> None:
        for index, source in enumerate(("interview", "platform_radar", "platform_radar")):
            merged = self._merge(
                {
                    "brand_id": "north-star",
                    "source": source,
                    "observed_at": "2026-08-0{}".format(index + 1),
                    "audience_insights": [{"audience": "通勤人群"}],
                },
                f"patch-{index}.json",
            )
            self.assertEqual(merged.returncode, 0, merged.stderr)

        provenance = json.loads(merged.stdout)["audience_insights"][0]["provenance"]
        self.assertEqual(provenance["observed_count"], 3)
        self.assertEqual(provenance["confidence"], "high")

    def test_platform_radar_cannot_write_differentiation_claims(self) -> None:
        merged = self._merge(
            {
                "brand_id": "north-star",
                "source": "platform_radar",
                "differentiation": [
                    {"vs": "竞品A", "point": "更温和", "evidence": "评论区说的"}
                ],
            }
        )

        self.assertEqual(merged.returncode, 2)
        self.assertIn("differentiation", merged.stderr)
        self.assertFalse(
            (self.output_root / "brands" / "north-star" / "insights.json").exists()
        )

    def test_unknown_product_id_is_rejected(self) -> None:
        merged = self._merge(
            {
                "brand_id": "north-star",
                "source": "interview",
                "content_pillars": [
                    {"pillar": "晨间效率护理", "product_ids": ["eye-cream"]}
                ],
            }
        )

        self.assertEqual(merged.returncode, 2)
        self.assertIn("eye-cream", merged.stderr)

    def test_resolve_returns_only_brand_level_and_matching_product_insights(self) -> None:
        merged = self._merge(
            {
                "brand_id": "north-star",
                "source": "interview",
                "audience_insights": [
                    {"audience": "品牌级人群"},
                    {"audience": "精华人群", "product_ids": ["daily-serum"]},
                    {"audience": "面霜人群", "product_ids": ["night-cream"]},
                ],
                "language_bank": {"hook_patterns": ["第二天不垮脸"]},
            }
        )
        self.assertEqual(merged.returncode, 0, merged.stderr)

        resolved = _run(
            "resolve",
            "--brand-id",
            "north-star",
            "--product-id",
            "daily-serum",
            "--output-root",
            str(self.output_root),
        )

        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        insights = json.loads(resolved.stdout)["insights"]
        self.assertEqual(
            [item["audience"] for item in insights["audience_insights"]],
            ["品牌级人群", "精华人群"],
        )
        self.assertEqual(insights["language_bank"]["hook_patterns"], ["第二天不垮脸"])

    def test_resolve_omits_insights_when_none_were_collected(self) -> None:
        resolved = _run(
            "resolve",
            "--brand-id",
            "north-star",
            "--product-id",
            "daily-serum",
            "--output-root",
            str(self.output_root),
        )

        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertNotIn("insights", json.loads(resolved.stdout))

    def test_merge_requires_an_existing_brand_profile(self) -> None:
        patch_file = self.root / "orphan.json"
        patch_file.write_text(
            json.dumps(
                {
                    "brand_id": "unknown-brand",
                    "source": "interview",
                    "audience_insights": [{"audience": "人群"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        merged = _run(
            "insights-merge",
            "--brand-id",
            "unknown-brand",
            "--patch-file",
            str(patch_file),
            "--output-root",
            str(self.output_root),
        )

        self.assertEqual(merged.returncode, 2)
        self.assertIn("品牌档案", merged.stderr)


if __name__ == "__main__":
    unittest.main()

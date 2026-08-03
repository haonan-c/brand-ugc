from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_image_post_pipeline import _plan, _write_inputs  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "ugc-image-post" / "scripts" / "run_pipeline.py"


def _profile() -> dict:
    return {
        "schema_version": 1,
        "brand_id": "north-star",
        "brand_name": "North Star",
        "visual": {"colors": ["#17324D", "#F7F3EC"]},
        "products": [
            {
                "product_id": "daily-serum",
                "name": "Daily Serum",
                "verified_claims": [
                    {"claim": "包装容量为30毫升", "evidence": "产品包装正面"}
                ],
            }
        ],
    }


def _insights(product_ids: list[str] | None = None) -> dict:
    entry = {
        "audience": "熬夜加班的25-30岁女性",
        "pain_points": ["第二天全脸暗沉"],
        "provenance": {
            "sources": ["interview"],
            "observed_count": 1,
            "first_seen": "2026-08-03",
            "last_seen": "2026-08-03",
            "confidence": "low",
        },
    }
    if product_ids is not None:
        entry["product_ids"] = product_ids
    return {
        "schema_version": 1,
        "brand_id": "north-star",
        "audience_insights": [entry],
    }


class ImagePostBrandInsightsTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        insights: dict | None,
        hook_basis: str | None,
        run_name: str,
    ) -> subprocess.CompletedProcess:
        reference, product, copy_file, plan_file = _write_inputs(root)
        plan = _plan()
        if hook_basis is not None:
            plan["hook_basis"] = hook_basis
        plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        brand_dir = root / "brands" / "north-star"
        brand_dir.mkdir(parents=True, exist_ok=True)
        profile_file = brand_dir / "profile.json"
        profile_file.write_text(
            json.dumps(_profile(), ensure_ascii=False), encoding="utf-8"
        )
        if insights is not None:
            (brand_dir / "insights.json").write_text(
                json.dumps(insights, ensure_ascii=False), encoding="utf-8"
            )

        return subprocess.run(
            [
                sys.executable,
                str(PIPELINE),
                "--run-name",
                run_name,
                "--reference-image",
                str(reference),
                "--reference-copy-file",
                str(copy_file),
                "--product-image",
                str(product),
                "--plan-file",
                str(plan_file),
                "--brand-profile-file",
                str(profile_file),
                "--product-id",
                "daily-serum",
                "--output-root",
                str(root / ".brand_ugc"),
                "--offline",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_hook_basis_is_required_once_insights_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                Path(tmp),
                insights=_insights(),
                hook_basis=None,
                run_name="missing-hook-basis",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("hook_basis", result.stderr)

    def test_hook_basis_outside_the_insights_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                Path(tmp),
                insights=_insights(),
                hook_basis="随口编的一个痛点",
                run_name="unknown-hook-basis",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("随口编的一个痛点", result.stderr)

    def test_grounded_hook_basis_reaches_the_brand_task_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run(
                root,
                insights=_insights(),
                hook_basis="第二天全脸暗沉",
                run_name="grounded-hook",
            )
            context = json.loads(
                (
                    root / ".brand_ugc" / "grounded-hook" / "outputs" / "品牌任务上下文.json"
                ).read_text(encoding="utf-8")
            )
            plan_markdown = (
                root / ".brand_ugc" / "grounded-hook" / "outputs" / "内容方案.md"
            ).read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            context["insights"]["audience_insights"][0]["pain_points"],
            ["第二天全脸暗沉"],
        )
        self.assertIn("钩子依据：第二天全脸暗沉", plan_markdown)

    def test_insights_for_another_product_do_not_constrain_this_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run(
                root,
                insights=_insights(product_ids=["night-cream"]),
                hook_basis=None,
                run_name="other-product-insights",
            )
            context = json.loads(
                (
                    root
                    / ".brand_ugc"
                    / "other-product-insights"
                    / "outputs"
                    / "品牌任务上下文.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("insights", context)

    def test_runs_without_insights_stay_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run(
                root,
                insights=None,
                hook_basis=None,
                run_name="no-insights",
            )
            context = json.loads(
                (
                    root / ".brand_ugc" / "no-insights" / "outputs" / "品牌任务上下文.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("insights", context)


if __name__ == "__main__":
    unittest.main()

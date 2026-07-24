from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "ugc-image-post" / "scripts" / "run_pipeline.py"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACAQMAAABIeJ9nAAAAIGNIUk0AAHomAACA"
    "hAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAAGUExURdjk7P///xpJngAA"
    "AAABYktHRAH/Ai3eAAAAB3RJTUUH6gcYCAEtDlENqAAAACV0RVh0ZGF0ZTpjcmVh"
    "dGUAMjAyNi0wNy0yNFQwODowMTo0NSswMDowMFft8ncAAAAldEVYdGRhdGU6bW9k"
    "aWZ5ADIwMjYtMDctMjRUMDg6MDE6NDUrMDA6MDAmsErLAAAAKHRFWHRkYXRlOnRp"
    "bWVzdGFtcAAyMDI2LTA3LTI0VDA4OjAxOjQ1KzAwOjAwcaVrFAAAAAxJREFUCNdj"
    "YGBgAAAABAABJzQnCgAAAABJRU5ErkJggg=="
)


def _plan() -> dict:
    roles = [
        ("cover", "cover-title"),
        ("context", "statement"),
        ("product", "product-hero"),
        ("benefit", "bullet-list"),
        ("usage", "steps"),
        ("cta", "summary-cta"),
    ]
    pages = []
    for index, (role, layout) in enumerate(roles, 1):
        pages.append(
            {
                "index": index,
                "role": role,
                "layout": layout,
                "headline": f"第{index}页标题",
                "body": f"第{index}页正文",
                "emphasis": [],
                "visual_prompt": f"为第{index}页生成留白充足的护肤场景，不含文字。",
                "product_mode": "real_composite" if index in {1, 3, 4} else "none",
                "fact_refs": ["包装容量为30毫升"] if index == 4 else [],
            }
        )
    return {
        "schema_version": 1,
        "adaptation_summary": "借鉴问题到解决方案的结构，全部文案重新创作。",
        "title_options": ["通勤护肤别再堆步骤", "六张图看懂晨间护理", "我的精简护理思路"],
        "selected_title": "通勤护肤别再堆步骤",
        "body_copy": "围绕已核实产品信息整理的一篇通勤护理笔记。",
        "hashtags": ["#日常护理", "#通勤护肤"],
        "cta": "收藏备用",
        "facts_used": [
            {
                "fact": "包装容量为30毫升",
                "source": "product_image_visible",
                "evidence": "用户提供的产品包装正面",
            }
        ],
        "needs_confirmation": [],
        "pages": pages,
    }


def _write_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    reference = root / "reference.png"
    product = root / "product.png"
    reference.write_bytes(PNG_1X1)
    product.write_bytes(PNG_1X1)
    copy_file = root / "reference-copy.txt"
    copy_file.write_text("对标文案，仅用于分析内容结构。", encoding="utf-8")
    plan_file = root / "plan.json"
    plan_file.write_text(
        json.dumps(_plan(), ensure_ascii=False),
        encoding="utf-8",
    )
    return reference, product, copy_file, plan_file


def _write_fake_generator(root: Path) -> Path:
    fake_generator = root / "fake_image_generator.py"
    fake_generator.write_text(
        """
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACAQMAAABIeJ9nAAAAIGNIUk0AAHomAACA"
    "hAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAAGUExURdjk7P///xpJngAA"
    "AAABYktHRAH/Ai3eAAAAB3RJTUUH6gcYCAEtDlENqAAAACV0RVh0ZGF0ZTpjcmVh"
    "dGUAMjAyNi0wNy0yNFQwODowMTo0NSswMDowMFft8ncAAAAldEVYdGRhdGU6bW9k"
    "aWZ5ADIwMjYtMDctMjRUMDg6MDE6NDUrMDA6MDAmsErLAAAAKHRFWHRkYXRlOnRp"
    "bWVzdGFtcAAyMDI2LTA3LTI0VDA4OjAxOjQ1KzAwOjAwcaVrFAAAAAxJREFUCNdj"
    "YGBgAAAABAABJzQnCgAAAABJRU5ErkJggg=="
)
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
args, _ = parser.parse_known_args()
output = Path(args.output_dir)
output.mkdir(parents=True, exist_ok=True)
(output / "image-01.png").write_bytes(PNG)
(output / "task.json").write_text(json.dumps({"task_id": output.name}), encoding="utf-8")
counter = Path(__file__).with_suffix(".count")
count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
counter.write_text(str(count + 1), encoding="utf-8")
print(json.dumps({"images": [str(output / "image-01.png")]}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return fake_generator


class ImagePostPipelineTests(unittest.TestCase):
    def test_brand_profile_fact_not_in_verified_claims_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, product, copy_file, plan_file = _write_inputs(root)
            plan = _plan()
            plan["facts_used"] = [
                {
                    "fact": "七天见效",
                    "source": "brand_profile",
                    "evidence": "品牌档案",
                }
            ]
            plan["pages"][3]["fact_refs"] = ["七天见效"]
            plan_file.write_text(
                json.dumps(plan, ensure_ascii=False),
                encoding="utf-8",
            )
            profile_file = root / "profile.json"
            profile_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "brand_id": "north-star",
                        "brand_name": "North Star",
                        "visual": {"colors": ["#17324D", "#F7F3EC"]},
                        "products": [
                            {
                                "product_id": "daily-serum",
                                "name": "Daily Serum",
                                "verified_claims": [
                                    {
                                        "claim": "包装容量为30毫升",
                                        "evidence": "产品包装正面",
                                    }
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PIPELINE),
                    "--run-name",
                    "unsupported-claim",
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

        self.assertEqual(result.returncode, 2)
        self.assertIn("七天见效", result.stderr)
        self.assertIn("未在品牌档案中核实", result.stderr)

    def test_unapproved_run_persists_plan_without_generating_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, product, copy_file, plan_file = _write_inputs(root)
            output_root = root / ".brand_ugc"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PIPELINE),
                    "--run-name",
                    "launch-post",
                    "--reference-image",
                    str(reference),
                    "--reference-copy-file",
                    str(copy_file),
                    "--product-image",
                    str(product),
                    "--plan-file",
                    str(plan_file),
                    "--output-root",
                    str(output_root),
                    "--offline",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            run_dir = output_root / "launch-post"
            plan_exists = (run_dir / "outputs" / "内容方案.md").is_file()
            deliverables_exist = (run_dir / "deliverables").exists()

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status"], "awaiting_approval")
        self.assertTrue(plan_exists)
        self.assertFalse(deliverables_exist)

    @unittest.skipUnless(shutil.which("magick"), "需要 ImageMagick")
    def test_approved_offline_run_delivers_six_composed_pages_and_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, product, copy_file, plan_file = _write_inputs(root)
            output_root = root / ".brand_ugc"
            base_command = [
                sys.executable,
                str(PIPELINE),
                "--run-name",
                "launch-post",
                "--reference-image",
                str(reference),
                "--reference-copy-file",
                str(copy_file),
                "--product-image",
                str(product),
                "--plan-file",
                str(plan_file),
                "--output-root",
                str(output_root),
                "--offline",
            ]
            subprocess.run(
                base_command,
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                [*base_command, "--approve", "--resume"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = output_root / "launch-post"
            page_files = sorted((run_dir / "deliverables").glob("page-*.png"))
            deliverables = sorted(
                path.name
                for path in (run_dir / "deliverables").iterdir()
                if path.is_file()
            )
            dimensions = subprocess.run(
                ["magick", "identify", "-format", "%wx%h", str(page_files[0])],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            qa = json.loads(
                (run_dir / "deliverables" / "QA报告.json").read_text(encoding="utf-8")
            )
            budget = json.loads(
                (run_dir / "state" / "request_budget.json").read_text(encoding="utf-8")
            )

        self.assertEqual(json.loads(completed.stdout)["status"], "completed")
        self.assertEqual(len(page_files), 6)
        self.assertEqual(dimensions, "1536x2048")
        self.assertEqual(
            deliverables,
            [
                "QA报告.json",
                "page-01.png",
                "page-02.png",
                "page-03.png",
                "page-04.png",
                "page-05.png",
                "page-06.png",
                "发布文案.md",
                "图文内容.json",
                "整组预览.png",
            ],
        )
        self.assertTrue(qa["pass"])
        self.assertEqual(qa["checks"]["page_count"], 6)
        self.assertEqual(qa["checks"]["real_product_pages"], [1, 3, 4])
        self.assertEqual(budget, {"maximum_image_requests": 8, "used": 0, "pages": {}})

    @unittest.skipUnless(shutil.which("magick"), "需要 ImageMagick")
    def test_online_generation_uses_six_requests_and_resume_does_not_resubmit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, product, copy_file, plan_file = _write_inputs(root)
            output_root = root / ".brand_ugc"
            fake_generator = _write_fake_generator(root)
            base_command = [
                sys.executable,
                str(PIPELINE),
                "--run-name",
                "online-post",
                "--reference-image",
                str(reference),
                "--reference-copy-file",
                str(copy_file),
                "--product-image",
                str(product),
                "--plan-file",
                str(plan_file),
                "--output-root",
                str(output_root),
                "--image-generator-script",
                str(fake_generator),
            ]
            subprocess.run(base_command, check=True, capture_output=True, text=True)
            first = subprocess.run(
                [*base_command, "--approve", "--resume"],
                check=False,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [*base_command, "--approve", "--resume"],
                check=False,
                capture_output=True,
                text=True,
            )
            budget = json.loads(
                (
                    output_root
                    / "online-post"
                    / "state"
                    / "request_budget.json"
                ).read_text(encoding="utf-8")
            )
            count = int(fake_generator.with_suffix(".count").read_text(encoding="utf-8"))

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(count, 6)
        self.assertEqual(budget["maximum_image_requests"], 8)
        self.assertEqual(budget["used"], 6)
        self.assertEqual(sorted(budget["pages"]), ["1", "2", "3", "4", "5", "6"])

    @unittest.skipUnless(shutil.which("magick"), "需要 ImageMagick")
    def test_visual_qa_retries_at_most_two_pages_then_accepts_a_pass_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference, product, copy_file, plan_file = _write_inputs(root)
            output_root = root / ".brand_ugc"
            fake_generator = _write_fake_generator(root)
            base_command = [
                sys.executable,
                str(PIPELINE),
                "--run-name",
                "qa-post",
                "--reference-image",
                str(reference),
                "--reference-copy-file",
                str(copy_file),
                "--product-image",
                str(product),
                "--plan-file",
                str(plan_file),
                "--output-root",
                str(output_root),
                "--image-generator-script",
                str(fake_generator),
            ]
            subprocess.run(base_command, check=True, capture_output=True, text=True)
            generated = subprocess.run(
                [*base_command, "--approve", "--resume"],
                check=False,
                capture_output=True,
                text=True,
            )
            failed_qa = root / "failed-qa.json"
            failed_qa.write_text(
                json.dumps(
                    {
                        "pass": False,
                        "issues": [
                            {
                                "page_index": 2,
                                "severity": "major",
                                "correction_prompt": "增加标题留白，不改变其他元素。",
                            },
                            {
                                "page_index": 4,
                                "severity": "major",
                                "correction_prompt": "让场景光线更自然，不添加文字。",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            retried = subprocess.run(
                [
                    *base_command,
                    "--approve",
                    "--resume",
                    "--visual-qa-file",
                    str(failed_qa),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            passed_qa = root / "passed-qa.json"
            passed_qa.write_text(
                json.dumps({"pass": True, "issues": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            accepted = subprocess.run(
                [
                    *base_command,
                    "--approve",
                    "--resume",
                    "--visual-qa-file",
                    str(passed_qa),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            run_dir = output_root / "qa-post"
            budget = json.loads(
                (run_dir / "state" / "request_budget.json").read_text(encoding="utf-8")
            )
            final_qa = json.loads(
                (run_dir / "deliverables" / "QA报告.json").read_text(encoding="utf-8")
            )
            count = int(fake_generator.with_suffix(".count").read_text(encoding="utf-8"))

        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertEqual(json.loads(generated.stdout)["status"], "awaiting_visual_qa")
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual(json.loads(retried.stdout)["status"], "awaiting_visual_qa")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["status"], "completed")
        self.assertEqual(count, 8)
        self.assertEqual(budget["used"], 8)
        self.assertEqual(budget["pages"]["2"]["attempts"], 2)
        self.assertEqual(budget["pages"]["4"]["attempts"], 2)
        self.assertTrue(final_qa["pass"])


if __name__ == "__main__":
    unittest.main()

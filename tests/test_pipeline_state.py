from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "brand-ugc" / "scripts"
PIPELINE = SCRIPTS / "run_public_pipeline.py"
PUBLIC_CONFIG = ROOT / "brand-ugc" / "config" / "public_gateway.json"
sys.path.insert(0, str(SCRIPTS))

from evolink_client import EvoLinkError  # noqa: E402
from run_public_pipeline import (  # noqa: E402
    _run_image_with_qa,
    parse_args,
    prepare_run_directory,
)


class ResumeContractTests(unittest.TestCase):
    def test_cli_reports_missing_media_tools_before_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "reference.mp4"
            product = root / "product.jpg"
            video.write_bytes(b"video")
            product.write_bytes(b"image")
            config = root / "public_gateway.json"
            config.write_text(
                PUBLIC_CONFIG.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            empty_path = root / "empty-path"
            empty_path.mkdir()
            output_root = root / "output"
            env = os.environ.copy()
            env["PATH"] = str(empty_path)
            env.pop("EVOLINK_API_KEY", None)
            env.pop("IMAGEGEN_API_KEY", None)

            result = subprocess.run(
                [
                    sys.executable,
                    str(PIPELINE),
                    "--run-name",
                    "安装检查",
                    "--video",
                    str(video),
                    "--product-image",
                    str(product),
                    "--config",
                    str(config),
                    "--output-root",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("缺少运行依赖", result.stderr)
        self.assertIn("ffmpeg", result.stderr)
        self.assertIn("ffprobe", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output_root.exists())

    def test_cli_defaults_to_hidden_project_output_directory(self) -> None:
        argv = [
            "run_public_pipeline.py",
            "--run-name",
            "案例 A",
            "--video",
            "reference.mp4",
            "--product-image",
            "product.png",
        ]

        with patch.object(sys, "argv", argv):
            args = parse_args()

        self.assertEqual(args.output_root, ".brand_ugc")

    def test_existing_run_requires_explicit_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "案例 A"
            prepared = prepare_run_directory(run_dir, resume=False)
            self.assertEqual(prepared, run_dir)
            (run_dir / "progress.json").write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "--resume"):
                prepare_run_directory(run_dir, resume=False)

            self.assertEqual(
                prepare_run_directory(run_dir, resume=True),
                run_dir,
            )

    def test_failed_reference_upload_does_not_consume_model_budget(self) -> None:
        class FailingUploadClient:
            def upload_image(self, path):
                raise EvoLinkError("upload blocked")

            def generate_image(self, **kwargs):
                raise AssertionError("图片上传失败后不应提交生图任务")

        class RecordingBudget:
            def __init__(self) -> None:
                self.labels = []

            def consume(self, label):
                self.labels.append(label)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference.jpg"
            reference.write_bytes(b"fixture")
            budget = RecordingBudget()

            with self.assertRaisesRegex(EvoLinkError, "upload blocked"):
                _run_image_with_qa(
                    client=FailingUploadClient(),
                    budget=budget,
                    stage_key="test_image",
                    prompt="生成十二宫格",
                    qa_reference_name="04-template-image.md",
                    reference_images=[reference],
                    qa_media=[],
                    images_dir=root / "images",
                    state_dir=root / "state",
                    qa_dir=root / "qa",
                    resolution="2K",
                    poll_interval=0,
                    poll_timeout=1,
                )

        self.assertEqual(budget.labels, [])


if __name__ == "__main__":
    unittest.main()

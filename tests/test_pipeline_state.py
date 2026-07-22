from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "brand-ugc" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evolink_client import EvoLinkError  # noqa: E402
from run_public_pipeline import _run_image_with_qa, prepare_run_directory  # noqa: E402


class ResumeContractTests(unittest.TestCase):
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

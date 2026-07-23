from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGES = ROOT / "ugc-storyboard" / "references" / "stages"


class BrandedProductPromptContractTests(unittest.TestCase):
    def test_real_product_packaging_marks_are_preserved_without_overlay_logos(self) -> None:
        shot_prompts = (STAGES / "03-shot-prompts.md").read_text(encoding="utf-8")
        final_image = (STAGES / "05-final-image.md").read_text(encoding="utf-8")
        video_prompt = (STAGES / "06-video-prompt.md").read_text(encoding="utf-8")

        for text in (shot_prompts, final_image, video_prompt):
            self.assertIn("包装固有品牌标识", text)
            self.assertIn("额外叠加", text)


if __name__ == "__main__":
    unittest.main()

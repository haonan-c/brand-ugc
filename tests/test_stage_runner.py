from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "ugc-storyboard"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from run_public_stage import run_structured_stage  # noqa: E402
from tests.test_contracts import valid_analysis  # noqa: E402


class _RepairingFakeClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_content(self, prompt, media_files, **kwargs):
        self.prompts.append(prompt)
        payload = valid_analysis()
        if len(self.prompts) == 1:
            payload["shots"].pop()
        return json.dumps(payload, ensure_ascii=False), {
            "model": "gemini-3.1-pro-preview",
            "status": "completed",
            "usage": {},
            "output": json.dumps(payload, ensure_ascii=False),
        }


class StructuredStageContractTests(unittest.TestCase):
    def test_invalid_first_response_is_repaired_once_before_rendering(self) -> None:
        client = _RepairingFakeClient()
        consumed: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_output = root / "analysis.json"
            text_output = root / "analysis.md"
            trace_output = root / "analysis.raw.json"

            payload = run_structured_stage(
                client=client,
                stage_name="analysis",
                prompt="分析视频并输出十二分镜。",
                media_files=[],
                schema_path=SKILL_DIR / "schemas" / "analysis.schema.json",
                json_output=json_output,
                text_output=text_output,
                trace_output=trace_output,
                renderer="analysis",
                timeline=True,
                consume_request=consumed.append,
            )

            persisted = json.loads(json_output.read_text(encoding="utf-8"))
            rendered = text_output.read_text(encoding="utf-8")
            trace = json.loads(trace_output.read_text(encoding="utf-8"))

        self.assertEqual(len(client.prompts), 2)
        for prompt in client.prompts:
            self.assertIn("【输出 JSON Schema】", prompt)
            self.assertIn('"summary"', prompt)
            self.assertIn('"audio"', prompt)
        self.assertIn("修复", client.prompts[1])
        self.assertEqual(consumed, ["analysis", "analysis_schema_repair"])
        self.assertEqual(len(payload["shots"]), 12)
        self.assertEqual(persisted, payload)
        self.assertEqual(rendered.count("### 分镜"), 12)
        self.assertEqual(len(trace["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()

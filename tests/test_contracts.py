from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "ugc-storyboard"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from contracts import (  # noqa: E402
    ContractError,
    load_schema,
    parse_json_response,
    render_analysis_markdown,
    validate_payload,
)


def valid_analysis() -> dict:
    shots = []
    for index in range(1, 13):
        start = (index - 1) * 1.25
        end = index * 1.25
        shots.append(
            {
                "index": index,
                "source": "observed",
                "start_seconds": start,
                "end_seconds": end,
                "visual_description": f"镜头{index}的可见画面",
                "shot_size": "close_up",
                "camera_movement": "static",
                "composition": "主体居中",
                "action": "展示产品",
                "product_presence": True,
                "person_presence": False,
                "on_screen_text": "",
                "audio_cue": "",
                "adaptation_function": "建立产品认知",
            }
        )
    return {
        "duration_seconds": 15,
        "summary": "十五秒电商视频",
        "audio": {
            "has_audio": True,
            "voiceover_summary": "简洁产品介绍",
            "music_mood": "轻快",
            "transcript": [],
        },
        "shots": shots,
    }


class StoryboardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load_schema(SKILL_DIR / "schemas" / "analysis.schema.json")

    def test_analysis_requires_exactly_twelve_ordered_non_overlapping_shots(self) -> None:
        payload = valid_analysis()
        validate_payload(payload, self.schema, timeline=True)

        too_short = copy.deepcopy(payload)
        too_short["shots"].pop()
        with self.assertRaisesRegex(ContractError, r"\$\.shots"):
            validate_payload(too_short, self.schema, timeline=True)

        overlapping = copy.deepcopy(payload)
        overlapping["shots"][1]["start_seconds"] = 1.0
        with self.assertRaisesRegex(ContractError, "重叠"):
            validate_payload(overlapping, self.schema, timeline=True)

        gap = copy.deepcopy(payload)
        gap["shots"][1]["start_seconds"] = 1.5
        with self.assertRaisesRegex(ContractError, "缺口"):
            validate_payload(gap, self.schema, timeline=True)

    def test_validated_analysis_renders_existing_markdown_time_contract(self) -> None:
        payload = valid_analysis()
        validate_payload(payload, self.schema, timeline=True)
        rendered = render_analysis_markdown(payload)

        self.assertEqual(rendered.count("### 分镜"), 12)
        self.assertIn('时间: "0:00.000-0:01.250"', rendered)
        self.assertIn("来源: observed（直接观察）", rendered)
        self.assertIn("音频分析", rendered)


class ImageQaContractTests(unittest.TestCase):
    def test_pass_cannot_be_true_when_a_required_check_failed(self) -> None:
        schema = load_schema(SKILL_DIR / "schemas" / "image_qa.schema.json")
        payload = {
            "pass": True,
            "grid": {"columns": 3, "rows": 4, "panels": 12, "order_correct": True},
            "checks": {
                "clean_frame": True,
                "composition_match": True,
                "product_consistency": False,
                "person_consistency": True,
                "realistic_background": True,
                "shot_mapping": True,
            },
            "issues": [
                {
                    "shot_index": 3,
                    "severity": "major",
                    "category": "product",
                    "description": "产品外观不一致",
                }
            ],
            "correction_prompt": "修正第3格产品外观。",
        }
        with self.assertRaisesRegex(ContractError, "pass=true"):
            validate_payload(payload, schema)


class JsonResponseRecoveryTests(unittest.TestCase):
    def test_recovers_only_missing_trailing_container_closers(self) -> None:
        self.assertEqual(
            parse_json_response('{"pass": true, "issues": []'),
            {"pass": True, "issues": []},
        )

    def test_does_not_repair_internal_json_corruption(self) -> None:
        with self.assertRaises(ContractError):
            parse_json_response('{"pass" true, "issues": []}')


if __name__ == "__main__":
    unittest.main()

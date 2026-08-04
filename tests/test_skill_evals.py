from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_SKILLS = ("ask-brand", "ugc-image-post", "ugc-storyboard")


class SkillEvalsTests(unittest.TestCase):
    def test_declared_skills_ship_an_evals_file(self) -> None:
        for skill in EVAL_SKILLS:
            with self.subTest(skill=skill):
                self.assertTrue((ROOT / skill / "evals" / "evals.json").is_file())

    def test_every_evals_file_is_well_formed(self) -> None:
        for path in sorted(ROOT.glob("*/evals/evals.json")):
            with self.subTest(path=str(path.relative_to(ROOT))):
                payload = json.loads(path.read_text(encoding="utf-8"))
                skill = path.parents[1].name
                self.assertEqual(payload["skill"], skill)
                self.assertEqual(payload["version"], 1)
                evals = payload["evals"]
                self.assertIsInstance(evals, list)
                self.assertGreater(len(evals), 0)
                ids = [case["id"] for case in evals]
                self.assertEqual(len(ids), len(set(ids)))
                for case in evals:
                    self.assertTrue(case["id"].strip())
                    self.assertTrue(case["prompt"].strip())
                    self.assertIsInstance(case["expected"], list)
                    self.assertGreater(len(case["expected"]), 0)
                    for expectation in case["expected"]:
                        self.assertIsInstance(expectation, str)
                        self.assertTrue(expectation.strip())

    def test_evals_skill_names_match_skill_frontmatter(self) -> None:
        for path in sorted(ROOT.glob("*/evals/evals.json")):
            skill_md = path.parents[1] / "SKILL.md"
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(skill_md.is_file())
                name_line = next(
                    line
                    for line in skill_md.read_text(encoding="utf-8").splitlines()
                    if line.startswith("name:")
                )
                declared = name_line.split(":", 1)[1].strip()
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["skill"], declared)


if __name__ == "__main__":
    unittest.main()

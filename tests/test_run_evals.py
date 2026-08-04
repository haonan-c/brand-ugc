from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run_evals.py"


def _write_fake_agent(root: Path, transcript: str) -> Path:
    path = root / "fake_agent.py"
    path.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"print({transcript!r})\n"
        "counter = Path(__file__).with_suffix('.count')\n"
        "count = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(count + 1))\n",
        encoding="utf-8",
    )
    return path


def _write_fake_judge(root: Path, body: str) -> Path:
    path = root / "fake_judge.py"
    path.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "prompt = Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "count = prompt.count('\\n')\n"
        f"print({body!r})\n",
        encoding="utf-8",
    )
    return path


def _judge_all(met: bool, total: int) -> str:
    entries = [
        {"index": index, "met": met, "evidence": "记录第 3 行"} for index in range(total)
    ]
    return json.dumps({"expectations": entries, "notes": "自动判定"}, ensure_ascii=False)


class RunEvalsTests(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_dry_run_writes_prompts_without_executing_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _write_fake_agent(root, "不应该被执行")
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ]
            )
            agent_ran = agent.with_suffix(".count").exists()
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            prompts = sorted(output_dir.glob("*/agent.prompt.txt"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(agent_ran)
        self.assertEqual(report["summary"]["skipped"], report["summary"]["total"])
        self.assertEqual(len(prompts), report["summary"]["total"])
        self.assertTrue(all(case["verdict"] == "skipped" for case in report["cases"]))

    def test_passing_judge_marks_case_pass_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = json.loads(
                (ROOT / "ask-brand" / "evals" / "evals.json").read_text(encoding="utf-8")
            )["evals"]
            case = next(item for item in expected if item["id"] == "ambiguous-asks-one-question")
            agent = _write_fake_agent(root, "我建议先做选题雷达。你的产品主要面向哪类人群？")
            judge = _write_fake_judge(root, _judge_all(True, len(case["expected"])))
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "ambiguous-asks-one-question",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            judgement = json.loads(
                (
                    output_dir / "ambiguous-asks-one-question" / "judgement.json"
                ).read_text(encoding="utf-8")
            )
            markdown = (output_dir / "report.md").read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["summary"], {
            "total": 1,
            "pass": 1,
            "fail": 0,
            "error": 0,
            "skipped": 0,
        })
        self.assertEqual(len(judgement["expectations"]), len(case["expected"]))
        self.assertEqual(judgement["expectations"][0]["expectation"], case["expected"][0])
        self.assertIn("ambiguous-asks-one-question", markdown)

    def test_failing_judge_reports_unmet_expectations_and_exit_code_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = json.loads(
                (ROOT / "ask-brand" / "evals" / "evals.json").read_text(encoding="utf-8")
            )["evals"]
            case = next(item for item in expected if item["id"] == "explicit-format-goes-direct")
            agent = _write_fake_agent(root, "我先帮你做一轮选题研究。")
            judge = _write_fake_judge(root, _judge_all(False, len(case["expected"])))
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "explicit-format-goes-direct",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["summary"]["fail"], 1)
        self.assertEqual(report["cases"][0]["unmet"], case["expected"])

    def test_judge_json_wrapped_in_a_code_fence_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = json.loads(
                (ROOT / "ugc-image-post" / "evals" / "evals.json").read_text(
                    encoding="utf-8"
                )
            )["evals"]
            case = next(item for item in expected if item["id"] == "no-publishing")
            agent = _write_fake_agent(root, "我只产出候选稿，不发布到平台。")
            judge = _write_fake_judge(
                root,
                "判定结果如下：\n```json\n"
                + _judge_all(True, len(case["expected"]))
                + "\n```\n",
            )
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ugc-image-post",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "no-publishing",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["cases"][0]["verdict"], "pass")

    def test_judge_that_echoes_the_prompt_before_answering_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = json.loads(
                (ROOT / "ask-brand" / "evals" / "evals.json").read_text(encoding="utf-8")
            )["evals"]
            case = next(item for item in expected if item["id"] == "no-profile-does-not-block")
            agent = _write_fake_agent(root, "没有品牌档案也可以继续。")
            judge = root / "echoing_judge.py"
            judge.write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "print(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
                f"print({_judge_all(True, len(case['expected']))!r})\n",
                encoding="utf-8",
            )
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "no-profile-does-not-block",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            raw = (
                output_dir / "no-profile-does-not-block" / "judge.raw.txt"
            ).read_text(encoding="utf-8")

        self.assertIn("从 0 开始的序号", raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["cases"][0]["verdict"], "pass")

    def test_unparsable_judge_output_is_an_error_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _write_fake_agent(root, "任意回复")
            judge = _write_fake_judge(root, "抱歉，我无法判断。")
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "explicit-topic-research",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["summary"]["error"], 1)
        self.assertIn("裁判输出", report["cases"][0]["error"])

    def test_partial_judge_coverage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _write_fake_agent(root, "任意回复")
            judge = _write_fake_judge(root, _judge_all(True, 1))
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ugc-storyboard",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--judge-command",
                    f"{sys.executable} {judge} {{prompt_file}}",
                    "--case",
                    "twelve-shots-exactly",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["summary"]["error"], 1)
        self.assertIn("只判定了 1 条", report["cases"][0]["error"])

    def test_agent_failure_is_reported_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = root / "failing_agent.py"
            agent.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
            output_dir = root / "out"
            result = self._run(
                [
                    "--skill",
                    "ugc-image-post",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--case",
                    "no-publishing",
                    "--output-dir",
                    str(output_dir),
                ]
            )
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["cases"][0]["verdict"], "error")
        self.assertEqual(report["cases"][0]["agent_returncode"], 3)

    def test_unknown_case_id_stops_before_spending_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _write_fake_agent(root, "不应该被执行")
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    f"{sys.executable} {agent} {{prompt_file}}",
                    "--case",
                    "no-such-case",
                    "--output-dir",
                    str(root / "out"),
                ]
            )
            agent_ran = agent.with_suffix(".count").exists()

        self.assertEqual(result.returncode, 2)
        self.assertIn("no-such-case", result.stderr)
        self.assertFalse(agent_ran)

    def test_command_template_without_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                [
                    "--skill",
                    "ask-brand",
                    "--agent-command",
                    "echo hello",
                    "--max-cases",
                    "1",
                    "--output-dir",
                    str(Path(tmp) / "out"),
                ]
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("占位符", result.stderr)


if __name__ == "__main__":
    unittest.main()

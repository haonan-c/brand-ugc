#!/usr/bin/env python3
"""Run a Skill 的 evals.json：先执行 Agent，再用裁判逐条判定 expected。"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

JUDGE_TEMPLATE = """你是一个严格的评测员。下面是一次 Agent 会话的完整记录，\
以及这次会话必须满足的期望清单。

逐条判断每个期望是否被满足。只依据记录中实际出现的内容判断，不要推测 Agent
"应该会"做什么。记录里找不到证据时一律判为 false。

只输出 JSON，不要输出任何其他文字：
{{"expectations":[{{"index":<从 0 开始的序号>,"met":<true|false>,\
"evidence":"<记录中的原文片段；未满足时写明缺了什么>"}}],"notes":"<一句话总结>"}}

## 用户输入

{prompt}

## 期望清单

{expectations}

## 会话记录

{transcript}
"""


class EvalError(Exception):
    """可读的失败原因。"""


def load_cases(
    skill: str,
    *,
    case_ids: list[str],
    max_cases: int | None,
) -> tuple[Path, list[dict[str, Any]]]:
    evals_path = ROOT / skill / "evals" / "evals.json"
    if not evals_path.is_file():
        raise EvalError(f"找不到 evals 文件：{evals_path}")
    payload = json.loads(evals_path.read_text(encoding="utf-8"))
    cases = payload["evals"]
    if case_ids:
        known = {case["id"] for case in cases}
        missing = [case_id for case_id in case_ids if case_id not in known]
        if missing:
            raise EvalError(f"evals.json 中不存在这些 id：{'、'.join(missing)}")
        cases = [case for case in cases if case["id"] in case_ids]
    if max_cases is not None:
        cases = cases[:max_cases]
    if not cases:
        raise EvalError("没有可执行的 case。")
    return evals_path, cases


def build_command(template: str, *, prompt: str, prompt_file: Path) -> list[str]:
    tokens = shlex.split(template)
    if not tokens:
        raise EvalError("命令模板为空。")
    if not any("{prompt}" in token or "{prompt_file}" in token for token in tokens):
        raise EvalError(
            "命令模板必须包含 {prompt} 或 {prompt_file} 占位符，"
            f"当前模板：{template}"
        )
    return [
        token.replace("{prompt_file}", str(prompt_file)).replace("{prompt}", prompt)
        for token in tokens
    ]


def run_command(command: list[str], *, timeout: int) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise EvalError(f"命令不存在：{command[0]}") from exc
    except subprocess.TimeoutExpired:
        return 124, f"命令超时（{timeout}s）：{shlex.join(command)}"
    transcript = result.stdout
    if result.stderr.strip():
        transcript += "\n[stderr]\n" + result.stderr
    return result.returncode, transcript


def extract_json(raw: str) -> dict[str, Any]:
    """取最后一个可解析的判定对象。

    很多 CLI 会把整个提示词连同回答一起回显，而提示词里就含有格式示例，
    所以不能用「第一个 { 到最后一个 }」来截取。
    """
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = raw.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(value, dict):
                objects.append(value)
        index = raw.find("{", index + 1)
    for value in reversed(objects):
        if "expectations" in value:
            return value
    if objects:
        return objects[-1]
    raise EvalError("裁判输出中找不到 JSON。")


def normalize_judgement(payload: dict[str, Any], expected: list[str]) -> dict[str, Any]:
    entries = payload.get("expectations")
    if not isinstance(entries, list):
        raise EvalError("裁判输出缺少 expectations 数组。")
    by_index: dict[int, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("met"), bool):
            raise EvalError("裁判输出的每条判定必须包含布尔 met。")
        index = entry.get("index")
        if not isinstance(index, int) or not 0 <= index < len(expected):
            raise EvalError(f"裁判输出的 index 越界：{index}")
        by_index[index] = entry
    if len(by_index) != len(expected):
        raise EvalError(
            f"裁判只判定了 {len(by_index)} 条，期望共 {len(expected)} 条。"
        )
    return {
        "expectations": [
            {
                "index": index,
                "expectation": expected[index],
                "met": by_index[index]["met"],
                "evidence": str(by_index[index].get("evidence", "")),
            }
            for index in range(len(expected))
        ],
        "notes": str(payload.get("notes", "")),
    }


def run_case(
    case: dict[str, Any],
    *,
    case_dir: Path,
    agent_template: str,
    judge_template: str,
    timeout: int,
    dry_run: bool,
) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    prompt = case["prompt"]
    expected = case["expected"]
    prompt_file = case_dir / "agent.prompt.txt"
    prompt_file.write_text(prompt + "\n", encoding="utf-8")
    agent_command = build_command(
        agent_template,
        prompt=prompt,
        prompt_file=prompt_file,
    )
    record: dict[str, Any] = {
        "id": case["id"],
        "prompt": prompt,
        "agent_command": shlex.join(agent_command),
        "dir": str(case_dir),
    }
    if dry_run:
        record["verdict"] = "skipped"
        return record

    returncode, transcript = run_command(agent_command, timeout=timeout)
    transcript_file = case_dir / "transcript.txt"
    transcript_file.write_text(transcript, encoding="utf-8")
    record["transcript"] = str(transcript_file)
    record["agent_returncode"] = returncode
    if returncode != 0:
        record["verdict"] = "error"
        record["error"] = f"Agent 命令退出码 {returncode}，详见 {transcript_file}"
        return record

    judge_prompt = JUDGE_TEMPLATE.format(
        prompt=prompt,
        expectations="\n".join(
            f"{index}. {item}" for index, item in enumerate(expected)
        ),
        transcript=transcript,
    )
    judge_prompt_file = case_dir / "judge.prompt.txt"
    judge_prompt_file.write_text(judge_prompt, encoding="utf-8")
    judge_command = build_command(
        judge_template,
        prompt=judge_prompt,
        prompt_file=judge_prompt_file,
    )
    record["judge_command"] = shlex.join(judge_command)
    judge_returncode, judge_output = run_command(judge_command, timeout=timeout)
    (case_dir / "judge.raw.txt").write_text(judge_output, encoding="utf-8")
    if judge_returncode != 0:
        record["verdict"] = "error"
        record["error"] = f"裁判命令退出码 {judge_returncode}。"
        return record
    try:
        judgement = normalize_judgement(extract_json(judge_output), expected)
    except (EvalError, json.JSONDecodeError) as exc:
        record["verdict"] = "error"
        record["error"] = f"裁判输出无法解析：{exc}"
        return record

    (case_dir / "judgement.json").write_text(
        json.dumps(judgement, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    unmet = [item for item in judgement["expectations"] if not item["met"]]
    record["verdict"] = "pass" if not unmet else "fail"
    record["met"] = len(expected) - len(unmet)
    record["total"] = len(expected)
    record["unmet"] = [item["expectation"] for item in unmet]
    record["notes"] = judgement["notes"]
    return record


def render_markdown(report: dict[str, Any]) -> str:
    icons = {"pass": "✅", "fail": "❌", "error": "⚠️", "skipped": "⏭️"}
    lines = [
        f"# {report['skill']} evals",
        "",
        f"运行时间：{report['generated_at']}",
        "",
        "| Case | 结果 | 满足 | 未满足的期望 |",
        "| --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        verdict = case["verdict"]
        met = (
            f"{case['met']}/{case['total']}"
            if "met" in case
            else case.get("error", "-")
        )
        unmet = "；".join(case.get("unmet", [])) or "-"
        lines.append(
            f"| `{case['id']}` | {icons.get(verdict, verdict)} {verdict} | {met} | {unmet} |"
        )
    summary = report["summary"]
    lines += [
        "",
        f"合计 {summary['total']} 条：通过 {summary['pass']}、"
        f"未通过 {summary['fail']}、异常 {summary['error']}、"
        f"跳过 {summary['skipped']}。",
        "",
    ]
    return "\n".join(lines)


def run_evals(args: argparse.Namespace) -> dict[str, Any]:
    _, cases = load_cases(
        args.skill,
        case_ids=args.case,
        max_cases=args.max_cases,
    )
    judge_template = args.judge_command or args.agent_command
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else ROOT / ".brand_ugc" / "evals" / args.skill / stamp
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for case in cases:
        record = run_case(
            case,
            case_dir=output_dir / case["id"],
            agent_template=args.agent_command,
            judge_template=judge_template,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        print(f"{record['verdict']:>7}  {record['id']}", file=sys.stderr)
        records.append(record)

    summary = {
        "total": len(records),
        "pass": sum(1 for item in records if item["verdict"] == "pass"),
        "fail": sum(1 for item in records if item["verdict"] == "fail"),
        "error": sum(1 for item in records if item["verdict"] == "error"),
        "skipped": sum(1 for item in records if item["verdict"] == "skipped"),
    }
    report = {
        "skill": args.skill,
        "generated_at": stamp,
        "dry_run": args.dry_run,
        "output_dir": str(output_dir),
        "cases": records,
        "summary": summary,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument(
        "--agent-command",
        required=True,
        help="执行 case 的命令模板，需包含 {prompt} 或 {prompt_file}。",
    )
    parser.add_argument(
        "--judge-command",
        help="裁判命令模板；省略时复用 --agent-command。",
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output-dir")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        report = run_evals(parse_args())
    except EvalError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["summary"]["fail"] or report["summary"]["error"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

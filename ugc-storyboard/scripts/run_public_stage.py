#!/usr/bin/env python3
"""Run one EvoLink-backed stage of the public ecommerce workflow."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_CONFIG = SKILL_DIR / "config" / "public_gateway.json"

from contracts import (  # noqa: E402
    ContractError,
    load_schema,
    parse_json_response,
    render_analysis_markdown,
    render_new_script_markdown,
    render_shot_prompts_markdown,
    render_video_prompt_text,
    validate_payload,
)
from evolink_client import EvoLinkClient, EvoLinkError, load_api_key  # noqa: E402


REF_RE = re.compile(r"【([^】]+)】")
MODULE_RE = re.compile(r"{{[^{}]+}}")
RENDERERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "analysis": render_analysis_markdown,
    "new_script": render_new_script_markdown,
    "shot_prompts": render_shot_prompts_markdown,
    "video_prompt": render_video_prompt_text,
}


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def write_json(path: str | Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def render_bracket_refs(template: str, contexts: dict[str, str]) -> str:
    """Render visible 【...】 inputs and reject all retired backend markers."""

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        if label not in contexts:
            return match.group(0)
        return f"【{label}】\n{contexts[label].strip() or '未上传/空'}"

    rendered = REF_RE.sub(replace, template)
    if MODULE_RE.search(rendered):
        raise ContractError("运行提示词中仍包含已废弃的 {{...Skill}} 模块标记。")
    return rendered


def parse_context(items: list[str]) -> dict[str, str]:
    contexts: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit("--context 必须使用 LABEL=path")
        label, path = item.split("=", 1)
        contexts[label.strip("【】 ")] = read_text(path)
    return contexts


def run_structured_stage(
    *,
    client: EvoLinkClient,
    stage_name: str,
    prompt: str,
    media_files: list[str | Path],
    schema_path: str | Path,
    json_output: str | Path,
    text_output: str | Path | None,
    trace_output: str | Path | None,
    renderer: str | None,
    timeline: bool,
    consume_request: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Generate, validate, repair once, persist JSON, then render display output."""

    schema = load_schema(schema_path)
    contract_prompt = (
        f"{prompt}\n\n"
        "【输出 JSON Schema】\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "严格使用以上字段、类型、枚举与数量约束，只输出一个完整 JSON 对象。"
    )
    attempts: list[dict[str, Any]] = []
    current_prompt = contract_prompt
    last_error: ContractError | None = None
    for attempt in range(2):
        label = stage_name if attempt == 0 else f"{stage_name}_schema_repair"
        if consume_request:
            consume_request(label)
        text, trace = client.generate_content(
            current_prompt,
            media_files,
            schema=schema,
            request_id=label,
        )
        try:
            payload = parse_json_response(text)
            validate_payload(payload, schema, timeline=timeline)
        except ContractError as exc:
            last_error = exc
            attempts.append({**trace, "contract_status": "failed", "contract_error": str(exc)})
            if attempt == 1:
                if trace_output:
                    write_json(trace_output, {"stage": stage_name, "attempts": attempts})
                raise ContractError(
                    f"{stage_name} 经一次自动修复后仍不符合合同：{exc}"
                ) from exc
            current_prompt = (
                f"{contract_prompt}\n\n"
                "【结构修复任务】\n"
                f"上次输出未通过合同校验：{exc}\n"
                "只修复 JSON 结构和字段，不添加输入中没有的事实。"
                "重新输出完整 JSON，不要解释、不要 Markdown 代码块。\n\n"
                f"【上次输出】\n{text}"
            )
            continue

        attempts.append({**trace, "contract_status": "passed"})
        write_json(json_output, payload)
        if text_output:
            if renderer:
                write_text(text_output, RENDERERS[renderer](payload))
            else:
                write_json(text_output, payload)
        if trace_output:
            write_json(trace_output, {"stage": stage_name, "attempts": attempts})
        return payload

    raise ContractError(f"{stage_name} 合同校验失败：{last_error}")


def load_runtime(config_path: str | Path) -> tuple[dict[str, Any], EvoLinkClient]:
    path = Path(config_path).expanduser().resolve()
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    api = config["api"]
    key_file = (path.parent / api["api_key_file"]).resolve()
    client = EvoLinkClient(
        api_key=load_api_key(key_file),
        text_base_url=api["text_base_url"],
        api_base_url=api["api_base_url"],
        files_base_url=api["files_base_url"],
        text_model=config["models"]["analysis"],
        image_model=config["models"]["image"],
        timeout=int(api.get("request_timeout_seconds", 180)),
        retries=int(api.get("request_retries", 3)),
    )
    return config, client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_PUBLIC_CONFIG))
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-file")
    prompt_group.add_argument("--prompt-text")
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--image-file", action="append", default=[])
    parser.add_argument("--video-file")
    parser.add_argument("--audio-file")
    parser.add_argument("--as-base64", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gateway-model", help=argparse.SUPPRESS)
    parser.add_argument("--llm-model", help=argparse.SUPPRESS)
    parser.add_argument("--video-fps", type=float, default=0.5, help=argparse.SUPPRESS)
    parser.add_argument("--temperature", type=float, default=0.2, help=argparse.SUPPRESS)
    parser.add_argument("--top-p", type=float, default=0.9, help=argparse.SUPPRESS)
    parser.add_argument("--max-tokens", type=int, default=16000, help=argparse.SUPPRESS)
    parser.add_argument("--stage-name", default="public_stage")
    parser.add_argument("--schema")
    parser.add_argument("--json-output")
    parser.add_argument("--renderer", choices=sorted(RENDERERS))
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-output")
    args = parser.parse_args()

    _, client = load_runtime(args.config)
    template = args.prompt_text if args.prompt_text is not None else read_text(args.prompt_file)
    prompt = render_bracket_refs(template, parse_context(args.context))
    media = list(args.image_file)
    if args.video_file:
        media.append(args.video_file)
    if args.audio_file:
        media.append(args.audio_file)

    try:
        if args.schema:
            run_structured_stage(
                client=client,
                stage_name=args.stage_name,
                prompt=prompt,
                media_files=media,
                schema_path=args.schema,
                json_output=args.json_output or args.output,
                text_output=args.output,
                trace_output=args.raw_output,
                renderer=args.renderer,
                timeline=args.timeline,
            )
        else:
            text, trace = client.generate_content(prompt, media)
            write_text(args.output, text)
            if args.raw_output:
                write_json(args.raw_output, trace)
    except (EvoLinkError, ContractError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(str(Path(args.output).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

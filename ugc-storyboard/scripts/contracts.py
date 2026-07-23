#!/usr/bin/env python3
"""Small JSON Schema validator and render helpers for pipeline contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when model output violates a stage contract."""


def load_schema(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate(value: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")
    expected_types = [expected] if isinstance(expected, str) else (expected or [])
    if expected_types and not any(_matches_type(value, item) for item in expected_types):
        raise ContractError(f"{path}: 类型必须为 {'/'.join(expected_types)}")

    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: 值不在允许范围内")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ContractError(f"{path}.{key}: 缺少必填字段")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ContractError(f"{path}: 包含未定义字段 {extras[0]}")
        for key, child in value.items():
            if key in properties:
                _validate(child, properties[key], f"{path}.{key}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractError(f"{path}: 数量少于 {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ContractError(f"{path}: 数量多于 {schema['maxItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for index, child in enumerate(value):
                _validate(child, item_schema, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ContractError(f"{path}: 文本过短")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ContractError(f"{path}: 文本过长")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ContractError(f"{path}: 文本格式不符合要求")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractError(f"{path}: 小于最小值 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractError(f"{path}: 大于最大值 {schema['maximum']}")


def validate_payload(
    payload: Any,
    schema: dict[str, Any],
    *,
    timeline: bool = False,
) -> None:
    """Validate JSON Schema keywords used by this skill plus timeline semantics."""

    _validate(payload, schema, "$")
    if isinstance(payload, dict) and {"pass", "grid", "checks", "issues"} <= set(payload):
        grid_ok = (
            payload["grid"].get("columns") == 3
            and payload["grid"].get("rows") == 4
            and payload["grid"].get("panels") == 12
            and payload["grid"].get("order_correct") is True
        )
        checks_ok = all(value is True for value in payload["checks"].values())
        serious_issue = any(
            issue.get("severity") in {"major", "critical"}
            for issue in payload["issues"]
        )
        if payload["pass"] is True and not (grid_ok and checks_ok and not serious_issue):
            raise ContractError("$.pass: 检查失败或存在重大问题时不能设置 pass=true")
        if payload["pass"] is False and not str(payload.get("correction_prompt", "")).strip():
            raise ContractError("$.correction_prompt: QA 失败时必须给出纠错提示词")
    if not timeline:
        return
    shots = payload.get("shots", [])
    previous_end = 0.0
    for expected_index, shot in enumerate(shots, 1):
        if shot.get("index") != expected_index:
            raise ContractError(f"$.shots[{expected_index - 1}].index: 必须连续编号")
        start = float(shot["start_seconds"])
        end = float(shot["end_seconds"])
        if end <= start:
            raise ContractError(f"$.shots[{expected_index - 1}]: 结束时间必须晚于开始时间")
        if expected_index == 1 and start > 0.05:
            raise ContractError("$.shots[0]: 时间轴必须从 0 秒开始")
        if start < previous_end - 0.001:
            raise ContractError(f"$.shots[{expected_index - 1}]: 时间轴发生重叠")
        if expected_index > 1 and start > previous_end + 0.05:
            raise ContractError(f"$.shots[{expected_index - 1}]: 时间轴存在缺口")
        previous_end = end
    expected_duration = payload.get("duration_seconds")
    if expected_duration is not None and abs(previous_end - float(expected_duration)) > 0.1:
        raise ContractError("$.shots: 末镜头必须覆盖到视频结束")
    if expected_duration is None and not 14.0 <= previous_end <= 16.0:
        raise ContractError("$.shots: 十五秒流程的末镜头必须落在 14–16 秒")


def parse_json_response(text: str) -> Any:
    """Parse plain JSON or one fenced JSON block returned by a model."""

    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        if exc.pos >= len(stripped) - 1:
            stack: list[str] = []
            in_string = False
            escaped = False
            valid_prefix = True
            for character in stripped:
                if in_string:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False
                    continue
                if character == '"':
                    in_string = True
                elif character in "[{":
                    stack.append(character)
                elif character in "]}":
                    expected = "[" if character == "]" else "{"
                    if not stack or stack.pop() != expected:
                        valid_prefix = False
                        break
            if valid_prefix and not in_string and stack:
                closers = "".join("}" if item == "{" else "]" for item in reversed(stack))
                try:
                    return json.loads(stripped + closers)
                except json.JSONDecodeError:
                    pass
        raise ContractError(f"模型输出不是有效 JSON：{exc.msg}") from exc


def _timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def render_analysis_markdown(payload: dict[str, Any]) -> str:
    source_labels = {"observed": "直接观察", "derived": "合并/拆分推导"}
    lines = [
        "# 12镜头解析",
        "",
        f"- 视频时长: {payload['duration_seconds']:.3f} 秒",
        f"- 内容总结: {payload['summary']}",
        "",
        "## 音频分析",
        "",
        f"- 是否有音频: {'是' if payload['audio']['has_audio'] else '否'}",
        f"- 口播摘要: {payload['audio']['voiceover_summary'] or '无'}",
        f"- 音乐氛围: {payload['audio']['music_mood'] or '无'}",
    ]
    for item in payload["audio"]["transcript"]:
        lines.append(
            f"- {_timestamp(item['start_seconds'])}-{_timestamp(item['end_seconds'])}: "
            f"{item['text']}"
        )
    lines.extend(["", "## 分镜", ""])
    for shot in payload["shots"]:
        lines.extend(
            [
                f"### 分镜 {shot['index']}",
                "",
                f'时间: "{_timestamp(shot["start_seconds"])}-{_timestamp(shot["end_seconds"])}"',
                f"来源: {shot['source']}（{source_labels[shot['source']]}）",
                f"画面: {shot['visual_description']}",
                f"景别: {shot['shot_size']}",
                f"运镜: {shot['camera_movement']}",
                f"构图: {shot['composition']}",
                f"动作: {shot['action']}",
                f"产品出现: {'是' if shot['product_presence'] else '否'}",
                f"人物出现: {'是' if shot['person_presence'] else '否'}",
                f"画面文字: {shot['on_screen_text'] or '无'}",
                f"声音: {shot['audio_cue'] or '无'}",
                f"镜头功能: {shot['adaptation_function']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_new_script_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 新产品-12分镜脚本",
        "",
        f"- 产品摘要: {payload['product_summary']}",
        f"- 人物策略: {payload['person_policy']}",
        f"- 改编说明: {payload['adaptation_summary']}",
        "",
        "## 已使用产品事实",
    ]
    lines.extend(f"- {item}" for item in payload["facts_used"])
    if not payload["facts_used"]:
        lines.append("- 无")
    lines.extend(["", "## 需要确认", ""])
    lines.extend(f"- {item}" for item in payload["needs_confirmation"])
    if not payload["needs_confirmation"]:
        lines.append("- 无")
    lines.extend(["", "## 分镜", ""])
    for shot in payload["shots"]:
        lines.extend(
            [
                f"### 分镜 {shot['index']}",
                "",
                f'时间: "{_timestamp(shot["start_seconds"])}-{_timestamp(shot["end_seconds"])}"',
                f"节奏功能: {shot['beat']}",
                f"场景: {shot['scene']}",
                f"画面: {shot['visual_description']}",
                f"景别: {shot['shot_size']}",
                f"运镜: {shot['camera_movement']}",
                f"构图: {shot['composition']}",
                f"动作: {shot['action']}",
                f"产品要求: {shot['product_direction']}",
                f"人物要求: {shot['person_direction']}",
                f"文案: {shot['copy'] or '无'}",
                f"声音: {shot['audio_cue'] or '无'}",
                f"映射理由: {shot['mapping_rationale']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_shot_prompts_markdown(payload: dict[str, Any]) -> str:
    lock = payload["series_lock"]
    lines = [
        "# 1-12分镜提示词",
        "",
        "## 系列一致性锁",
        "",
        f"- 产品: {lock['product']}",
        f"- 人物: {lock['person']}",
        f"- 环境: {lock['environment']}",
        f"- 光线: {lock['lighting']}",
        f"- 色调: {lock['color_grade']}",
        "",
    ]
    for shot in payload["shots"]:
        lines.extend(
            [
                f"### 分镜 {shot['index']}",
                "",
                f'时间: "{_timestamp(shot["start_seconds"])}-{_timestamp(shot["end_seconds"])}"',
                f"画面提示词: {shot['image_prompt']}",
                f"负面约束: {shot['negative_prompt']}",
                f"运动意图: {shot['motion_intent']}",
                f"是否有产品: {'是' if shot['product_presence'] else '否'}",
                f"是否有人物: {'是' if shot['person_presence'] else '否'}",
                f"画面文字: {shot['on_screen_text'] or '无；不得烘焙文字'}",
                f"映射理由: {shot['mapping_rationale']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_video_prompt_text(payload: dict[str, Any]) -> str:
    lines = [
        payload["master_prompt"].strip(),
        "",
        "—— 12条分镜运动指令 ——",
        "",
    ]
    for shot in payload["shots"]:
        lines.append(
            f"{shot['index']:02d}. "
            f"{_timestamp(shot['start_seconds'])}-{_timestamp(shot['end_seconds'])}："
            f"{shot['motion_instruction']}"
        )
    return "\n".join(lines).rstrip() + "\n"

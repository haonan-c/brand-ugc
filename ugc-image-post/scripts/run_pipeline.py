#!/usr/bin/env python3
"""Run the local-first benchmark image-post workflow."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_LAYOUTS = {
    "cover-title",
    "product-hero",
    "statement",
    "bullet-list",
    "steps",
    "comparison",
    "detail-callout",
    "summary-cta",
}
ALLOWED_PRODUCT_MODES = {"real_composite", "ai_interaction", "none"}
SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE_GENERATOR = (
    SKILL_DIR.parent / "image-generator" / "scripts" / "generate_image.py"
)


class PipelineError(ValueError):
    """Raised when an image-post run violates its public contract."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"无法读取 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise PipelineError(f"JSON 顶层必须是对象：{path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_input(source: Path, target: Path) -> Path:
    if not source.is_file():
        raise PipelineError(f"输入文件不存在：{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if _digest(source) != _digest(target):
            raise PipelineError(f"恢复任务时输入发生变化：{source.name}")
        return target
    shutil.copy2(source, target)
    return target


def validate_plan(plan: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "adaptation_summary",
        "title_options",
        "selected_title",
        "body_copy",
        "hashtags",
        "cta",
        "facts_used",
        "needs_confirmation",
        "pages",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise PipelineError(f"内容方案缺少必填字段：{missing[0]}")
    if plan["schema_version"] != 1:
        raise PipelineError("内容方案 schema_version 当前只支持 1。")
    titles = plan["title_options"]
    if not isinstance(titles, list) or len(titles) != 3:
        raise PipelineError("title_options 必须恰好包含三个标题。")
    if plan["selected_title"] not in titles:
        raise PipelineError("selected_title 必须来自 title_options。")
    pages = plan["pages"]
    if not isinstance(pages, list) or not 4 <= len(pages) <= 9:
        raise PipelineError("pages 必须包含 4–9 页。")
    facts = plan["facts_used"]
    if not isinstance(facts, list):
        raise PipelineError("facts_used 必须是数组。")
    known_facts: set[str] = set()
    for index, item in enumerate(facts):
        if not isinstance(item, dict):
            raise PipelineError(f"facts_used[{index}] 必须是对象。")
        fact = item.get("fact")
        source = item.get("source")
        evidence = item.get("evidence")
        if not isinstance(fact, str) or not fact.strip():
            raise PipelineError(f"facts_used[{index}].fact 不能为空。")
        if source not in {"brand_profile", "user_provided", "product_image_visible"}:
            raise PipelineError(f"facts_used[{index}].source 不受支持。")
        if not isinstance(evidence, str) or not evidence.strip():
            raise PipelineError(f"facts_used[{index}].evidence 不能为空。")
        if fact in known_facts:
            raise PipelineError(f"facts_used 包含重复事实：{fact}")
        known_facts.add(fact)
    for expected, page in enumerate(pages, 1):
        if not isinstance(page, dict):
            raise PipelineError(f"pages[{expected - 1}] 必须是对象。")
        if page.get("index") != expected:
            raise PipelineError("pages 必须从 1 开始连续编号。")
        if page.get("layout") not in ALLOWED_LAYOUTS:
            raise PipelineError(f"第 {expected} 页使用了不支持的 layout。")
        if page.get("product_mode") not in ALLOWED_PRODUCT_MODES:
            raise PipelineError(f"第 {expected} 页使用了不支持的 product_mode。")
        for field in ("role", "headline", "body", "visual_prompt"):
            if not isinstance(page.get(field), str):
                raise PipelineError(f"第 {expected} 页的 {field} 必须是文本。")
        fact_refs = page.get("fact_refs")
        if not isinstance(fact_refs, list) or any(
            fact not in known_facts for fact in fact_refs
        ):
            raise PipelineError(f"第 {expected} 页引用了未列入 facts_used 的事实。")


def _resolve_brand_context(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    if not args.brand_profile_file:
        if any(item["source"] == "brand_profile" for item in plan["facts_used"]):
            raise PipelineError(
                "内容方案引用了 brand_profile 事实，但未提供 --brand-profile-file。"
            )
        return None
    profile_path = Path(args.brand_profile_file).expanduser().resolve()
    profile = read_json(profile_path)
    products = profile.get("products")
    if not isinstance(products, list):
        raise PipelineError("品牌档案 products 必须是数组。")
    if args.product_id:
        product = next(
            (item for item in products if item.get("product_id") == args.product_id),
            None,
        )
        if product is None:
            raise PipelineError(f"品牌档案中不存在产品：{args.product_id}")
    elif len(products) == 1:
        product = products[0]
    else:
        raise PipelineError("品牌档案包含多个产品时必须提供 --product-id。")
    verified = {
        item["claim"]
        for item in product.get("verified_claims", [])
        if isinstance(item, dict) and isinstance(item.get("claim"), str)
    }
    for item in plan["facts_used"]:
        if item["source"] == "brand_profile" and item["fact"] not in verified:
            raise PipelineError(
                f"事实“{item['fact']}”未在品牌档案中核实，不能用于营销内容。"
            )
    prohibited = set(
        (profile.get("compliance") or {}).get("prohibited_claims") or []
    ) | set(product.get("prohibited_expressions") or [])
    for item in plan["facts_used"]:
        if item["fact"] in prohibited:
            raise PipelineError(f"事实“{item['fact']}”命中品牌禁用表达。")
    return {
        "schema_version": profile.get("schema_version", 1),
        "brand_id": profile.get("brand_id", ""),
        "brand_name": profile.get("brand_name", ""),
        "audiences": profile.get("audiences", []),
        "voice": profile.get("voice", {}),
        "visual": profile.get("visual", {}),
        "compliance": profile.get("compliance", {}),
        "defaults": profile.get("defaults", {}),
        "product": product,
    }


def render_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# 图文内容方案",
        "",
        f"- 结构迁移说明：{plan['adaptation_summary']}",
        f"- 选定标题：{plan['selected_title']}",
        f"- CTA：{plan['cta']}",
        "",
        "## 标题候选",
        "",
    ]
    lines.extend(f"{index}. {title}" for index, title in enumerate(plan["title_options"], 1))
    lines.extend(["", "## 页面方案", ""])
    for page in plan["pages"]:
        lines.extend(
            [
                f"### 第 {page['index']} 页 · {page['role']}",
                "",
                f"- 版式：{page['layout']}",
                f"- 标题：{page['headline']}",
                f"- 正文：{page['body'] or '无'}",
                f"- 产品模式：{page['product_mode']}",
                f"- 视觉：{page['visual_prompt']}",
                f"- 产品事实：{'；'.join(page['fact_refs']) or '无'}",
                "",
            ]
        )
    if plan["needs_confirmation"]:
        lines.extend(["## 需要确认", ""])
        lines.extend(f"- {item}" for item in plan["needs_confirmation"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _image_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _wrap_text(value: str, max_chars: int, max_lines: int, *, label: str) -> list[str]:
    normalized = " ".join(value.split())
    if not normalized:
        return []
    lines: list[str] = []
    current = ""
    for character in normalized:
        if len(current) >= max_chars:
            lines.append(current)
            current = character
        else:
            current += character
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise PipelineError(f"{label} 排版后超过 {max_lines} 行，请缩短文案。")
    return lines


def _text_element(
    lines: list[str],
    *,
    x: int,
    y: int,
    font_size: int,
    line_height: int,
    weight: int,
    color: str,
) -> str:
    if not lines:
        return ""
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        tspans.append(
            f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>'
        )
    return (
        f'<text x="{x}" y="{y}" font-size="{font_size}" '
        f'font-weight="{weight}" fill="{color}">'
        + "".join(tspans)
        + "</text>"
    )


def _page_svg(
    *,
    page: dict[str, Any],
    background: Path,
    product: Path,
    width: int,
    height: int,
    palette: list[str],
    logo: Path | None,
    corner_radius: str,
) -> str:
    headline_lines = _wrap_text(
        page["headline"],
        12,
        3,
        label=f"第 {page['index']} 页标题",
    )
    body_lines = _wrap_text(
        page["body"],
        24,
        5,
        label=f"第 {page['index']} 页正文",
    )
    scale = width / 1536
    layouts = {
        "cover-title": (70, 90, 1396, 720, 112, 230, 720, 900, 720, 960),
        "product-hero": (70, 90, 1396, 620, 112, 220, 650, 650, 820, 1120),
        "statement": (110, 500, 1316, 820, 160, 690, 760, 1050, 620, 760),
        "bullet-list": (70, 160, 840, 1500, 120, 340, 900, 760, 560, 1050),
        "steps": (70, 170, 940, 1450, 120, 350, 980, 820, 500, 980),
        "comparison": (70, 120, 1396, 800, 112, 280, 760, 900, 650, 920),
        "detail-callout": (70, 100, 880, 900, 120, 280, 820, 720, 620, 1120),
        "summary-cta": (140, 420, 1256, 900, 200, 650, 760, 1080, 600, 720),
    }
    (
        panel_x,
        panel_y,
        panel_width,
        base_panel_height,
        text_x,
        title_y,
        product_x,
        product_y,
        product_width,
        product_height,
    ) = layouts[page["layout"]]
    body_y = title_y + len(headline_lines) * 118 + 86
    required_panel_height = 300 + len(headline_lines) * 118 + len(body_lines) * 72
    panel_height = round(
        max(base_panel_height, min(required_panel_height, 1500)) * scale
    )
    panel_x = round(panel_x * scale)
    panel_y = round(panel_y * scale)
    panel_width = round(panel_width * scale)
    text_x = round(text_x * scale)
    title_y = round(title_y * scale)
    body_y = round(body_y * scale)
    title_size = round(82 * scale)
    body_size = round(40 * scale)
    title_line = round(110 * scale)
    body_line = round(66 * scale)
    background_uri = _image_data_uri(background)
    product_element = ""
    if page["product_mode"] == "real_composite":
        product_uri = _image_data_uri(product)
        product_render_x = round(product_x * scale)
        product_render_y = round(product_y * scale)
        product_render_width = round(product_width * scale)
        product_render_height = round(product_height * scale)
        product_element = (
            f'<rect x="{product_render_x}" y="{product_render_y}" '
            f'width="{product_render_width}" height="{product_render_height}" '
            f'rx="{round(34 * scale)}" fill="#FFFFFF" opacity="0.98"/>'
            f'<image href="{product_uri}" x="{product_render_x}" '
            f'y="{product_render_y}" width="{product_render_width}" '
            f'height="{product_render_height}" preserveAspectRatio="xMidYMid meet"/>'
        )
    logo_element = ""
    if logo is not None:
        logo_element = (
            f'<image href="{_image_data_uri(logo)}" x="{round(width - 330 * scale)}" '
            f'y="{round(80 * scale)}" width="{round(220 * scale)}" '
            f'height="{round(120 * scale)}" preserveAspectRatio="xMidYMid meet"/>'
        )
    accent = palette[0] if palette else "#17324D"
    surface = palette[1] if len(palette) > 1 else "#F7F3EC"
    title = _text_element(
        headline_lines,
        x=text_x,
        y=title_y,
        font_size=title_size,
        line_height=title_line,
        weight=700,
        color=accent,
    )
    body = _text_element(
        body_lines,
        x=text_x,
        y=body_y,
        font_size=body_size,
        line_height=body_line,
        weight=400,
        color="#1F2933",
    )
    radius_values = {"none": 0, "small": 18, "medium": 42, "large": 72}
    radius = round(radius_values.get(corner_radius, 42) * scale)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<image href="{background_uri}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice"/>
<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF" opacity="0.16"/>
{product_element}
<rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" rx="{radius}" fill="{surface}" opacity="0.94"/>
<rect x="{panel_x}" y="{panel_y}" width="{round(18 * scale)}" height="{panel_height}" rx="{round(9 * scale)}" fill="{accent}"/>
{title}
{body}
{logo_element}
<text x="{round(112 * scale)}" y="{round(height - 92 * scale)}" font-size="{round(30 * scale)}" font-weight="500" fill="{accent}">0{page['index']}</text>
</svg>
"""


def _run_command(command: list[str], *, label: str) -> None:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PipelineError(f"{label}失败：{detail}")


def _font_path(preferred_fonts: list[str] | None = None) -> Path:
    preferred_fonts = preferred_fonts or []
    candidates: list[Path] = []
    for value in preferred_fonts:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            candidates.append(candidate.resolve())
        elif shutil.which("fc-match"):
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", value],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                candidates.append(Path(result.stdout.strip()))
    candidates = [
        *candidates,
        Path.home() / "Library/Fonts/NotoSansCJKsc-Regular.otf",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    if shutil.which("fc-match"):
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", "Noto Sans CJK SC"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            candidates.insert(0, Path(result.stdout.strip()))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PipelineError(
        "未找到支持中文的字体。请安装 Noto Sans CJK SC、苹方或微软雅黑。"
    )


def _canvas_size(resolution: str) -> tuple[int, int]:
    normalized = resolution.upper()
    if normalized == "2K":
        return 1536, 2048
    if normalized == "1K":
        return 768, 1024
    raise PipelineError("--resolution 仅允许 1K 或 2K；不会自动降级。")


def _offline_background(
    source: Path,
    output: Path,
    *,
    width: int,
    height: int,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        return output
    _run_command(
        [
            "magick",
            str(source),
            "-resize",
            f"{width}x{height}^",
            "-gravity",
            "center",
            "-extent",
            f"{width}x{height}",
            str(output),
        ],
        label="离线底图生成",
    )
    return output


def _online_backgrounds(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    plan: dict[str, Any],
    product: Path,
) -> dict[int, Path]:
    generator = Path(args.image_generator_script).expanduser().resolve()
    if not generator.is_file():
        raise PipelineError(
            "缺少 image-generator 脚本。请同时安装 image-generator Skill，"
            f"或使用 --image-generator-script 指定路径：{generator}"
        )
    budget_path = run_dir / "state" / "request_budget.json"
    budget = (
        read_json(budget_path)
        if budget_path.exists()
        else {
            "maximum_image_requests": len(plan["pages"]) + 2,
            "used": 0,
            "pages": {},
        }
    )
    budget["maximum_image_requests"] = len(plan["pages"]) + 2
    outputs: dict[int, Path] = {}
    for page in plan["pages"]:
        index = page["index"]
        output_dir = run_dir / "images" / "generated" / f"page-{index:02d}"
        output = output_dir / "image-01.png"
        if output.exists():
            outputs[index] = output
            continue
        if int(budget["used"]) >= int(budget["maximum_image_requests"]):
            raise PipelineError("本次任务已达到图片生成请求上限。")
        prompt = page["visual_prompt"].strip()
        if page["product_mode"] == "ai_interaction":
            prompt += (
                "\n使用参考产品完成真实交互场景，保持包装、颜色、Logo与标签一致。"
                "画面中不要生成字幕、营销文字、平台UI或水印。"
            )
        else:
            prompt += (
                "\n只生成无字场景底图，保留充足排版留白。"
                "不要生成产品、Logo、字幕、营销文字、平台UI或水印。"
            )
        prompt_file = run_dir / "prompts" / f"page-{index:02d}.prompt.txt"
        write_text(prompt_file, prompt + "\n")
        page_state = budget["pages"].setdefault(
            str(index),
            {"attempts": 0, "outputs": []},
        )
        page_state["attempts"] = int(page_state["attempts"]) + 1
        page_state["outputs"].append(str(output))
        budget["used"] = int(budget["used"]) + 1
        write_json(budget_path, budget)
        command = [
            sys.executable,
            str(generator),
            "--prompt-file",
            str(prompt_file),
            "--output-dir",
            str(output_dir),
            "--aspect-ratio",
            "3:4",
            "--resolution",
            args.resolution.upper(),
        ]
        if page["product_mode"] == "ai_interaction":
            command.extend(["--image-file", str(product)])
        _run_command(command, label=f"第 {index} 页生图")
        if not output.is_file():
            raise PipelineError(f"第 {index} 页生图未返回预期文件：{output}")
        outputs[index] = output
    write_json(budget_path, budget)
    return outputs


def _validate_visual_qa(payload: dict[str, Any], page_count: int) -> None:
    if not isinstance(payload.get("pass"), bool):
        raise PipelineError("视觉 QA 的 pass 必须是布尔值。")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise PipelineError("视觉 QA 的 issues 必须是数组。")
    for issue in issues:
        if not isinstance(issue, dict):
            raise PipelineError("视觉 QA issue 必须是对象。")
        index = issue.get("page_index")
        if not isinstance(index, int) or not 1 <= index <= page_count:
            raise PipelineError("视觉 QA issue 的 page_index 超出范围。")
        if issue.get("severity") not in {"minor", "major", "critical"}:
            raise PipelineError("视觉 QA issue 的 severity 不受支持。")
        if issue["severity"] in {"major", "critical"} and not str(
            issue.get("correction_prompt", "")
        ).strip():
            raise PipelineError("重大视觉 QA 问题必须提供 correction_prompt。")
    serious = [
        issue for issue in issues if issue.get("severity") in {"major", "critical"}
    ]
    if payload["pass"] and serious:
        raise PipelineError("存在 major/critical 问题时视觉 QA 不能 pass=true。")


def _invoke_generation(
    *,
    args: argparse.Namespace,
    page: dict[str, Any],
    prompt: str,
    prompt_file: Path,
    output_dir: Path,
    product: Path,
) -> Path:
    generator = Path(args.image_generator_script).expanduser().resolve()
    write_text(prompt_file, prompt.strip() + "\n")
    command = [
        sys.executable,
        str(generator),
        "--prompt-file",
        str(prompt_file),
        "--output-dir",
        str(output_dir),
        "--aspect-ratio",
        "3:4",
        "--resolution",
        args.resolution.upper(),
    ]
    if page["product_mode"] == "ai_interaction":
        command.extend(["--image-file", str(product)])
    _run_command(command, label=f"第 {page['index']} 页生图")
    output = output_dir / "image-01.png"
    if not output.is_file():
        raise PipelineError(f"生图未返回预期文件：{output}")
    return output


def _apply_visual_qa(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    plan: dict[str, Any],
    product: Path,
    backgrounds: dict[int, Path],
) -> tuple[dict[int, Path], dict[str, Any], str]:
    choice_path = run_dir / "state" / "background_choices.json"
    stored_choices = read_json(choice_path) if choice_path.exists() else {}
    for key, value in stored_choices.items():
        candidate = Path(value)
        if candidate.is_file():
            backgrounds[int(key)] = candidate
    write_json(choice_path, {str(key): str(value) for key, value in backgrounds.items()})
    if not args.visual_qa_file:
        return (
            backgrounds,
            {"pass": False, "status": "pending", "issues": []},
            "awaiting_visual_qa",
        )

    qa = read_json(Path(args.visual_qa_file).expanduser().resolve())
    _validate_visual_qa(qa, len(plan["pages"]))
    write_json(run_dir / "qa" / "visual_qa_input.json", qa)
    if qa["pass"]:
        accepted = dict(qa)
        accepted["status"] = "passed"
        return backgrounds, accepted, "completed"

    serious = [
        issue
        for issue in qa["issues"]
        if issue["severity"] in {"major", "critical"}
    ]
    retry_pages = list(dict.fromkeys(issue["page_index"] for issue in serious))
    if len(retry_pages) > 2:
        raise PipelineError(
            "整组有超过两页未通过视觉 QA；已停止自动纠错，请人工选择优先页面。"
        )
    budget_path = run_dir / "state" / "request_budget.json"
    budget = read_json(budget_path)
    pages_by_index = {page["index"]: page for page in plan["pages"]}
    for index in retry_pages:
        page = pages_by_index[index]
        page_state = budget["pages"][str(index)]
        if int(page_state["attempts"]) >= 2:
            raise PipelineError(f"第 {index} 页已经自动纠错一次，不能再次重生成。")
        if int(budget["used"]) >= int(budget["maximum_image_requests"]):
            raise PipelineError("本次任务已达到图片生成请求上限。")
        issue = next(item for item in serious if item["page_index"] == index)
        attempt = int(page_state["attempts"]) + 1
        output_dir = (
            run_dir
            / "images"
            / "generated"
            / f"page-{index:02d}-retry-{attempt - 1}"
        )
        output = output_dir / "image-01.png"
        if not output.exists():
            prompt = (
                page["visual_prompt"].strip()
                + "\n"
                + issue["correction_prompt"].strip()
                + "\n保持其他已正确元素不变；不要添加字幕、平台UI或水印。"
            )
            page_state["attempts"] = attempt
            page_state["outputs"].append(str(output))
            budget["used"] = int(budget["used"]) + 1
            write_json(budget_path, budget)
            output = _invoke_generation(
                args=args,
                page=page,
                prompt=prompt,
                prompt_file=run_dir
                / "prompts"
                / f"page-{index:02d}-retry-{attempt - 1}.prompt.txt",
                output_dir=output_dir,
                product=product,
            )
        backgrounds[index] = output
    write_json(budget_path, budget)
    write_json(choice_path, {str(key): str(value) for key, value in backgrounds.items()})
    pending = dict(qa)
    pending["status"] = "retry_generated_needs_review"
    pending["retry_pages"] = retry_pages
    write_json(run_dir / "qa" / "visual_qa_retry.json", pending)
    return backgrounds, pending, "awaiting_visual_qa"


def _compose_page(
    *,
    page: dict[str, Any],
    background: Path,
    product: Path,
    output_dir: Path,
    width: int,
    height: int,
    palette: list[str],
    attempt: int,
    logo: Path | None,
    font_path: Path,
    corner_radius: str,
) -> Path:
    output = output_dir / f"page-{page['index']:02d}-attempt-{attempt}.png"
    if output.exists():
        return output
    svg = output_dir / f"page-{page['index']:02d}-attempt-{attempt}.svg"
    write_text(
        svg,
        _page_svg(
            page=page,
            background=background,
            product=product,
            width=width,
            height=height,
            palette=palette,
            logo=logo,
            corner_radius=corner_radius,
        ),
    )
    _run_command(
        ["magick", "-font", str(font_path), str(svg), str(output)],
        label=f"第 {page['index']} 页排版",
    )
    return output


def _image_dimensions(path: Path) -> str:
    result = subprocess.run(
        ["magick", "identify", "-format", "%wx%h", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PipelineError(f"无法读取图片尺寸：{path}")
    return result.stdout


def _render_copy_markdown(plan: dict[str, Any]) -> str:
    tags = " ".join(plan["hashtags"])
    return (
        "# 发布文案\n\n"
        "## 标题候选\n\n"
        + "\n".join(
            f"{index}. {title}" for index, title in enumerate(plan["title_options"], 1)
        )
        + f"\n\n## 选定标题\n\n{plan['selected_title']}\n"
        + f"\n## 正文\n\n{plan['body_copy']}\n"
        + f"\n## CTA\n\n{plan['cta']}\n"
        + f"\n## 话题标签\n\n{tags}\n"
    )


def _brand_visual(
    args: argparse.Namespace,
) -> tuple[list[str], Path | None, list[str], str]:
    if not args.brand_profile_file:
        return ["#17324D", "#F7F3EC"], None, [], "medium"
    profile_path = Path(args.brand_profile_file).expanduser().resolve()
    profile = read_json(profile_path)
    colors = ((profile.get("visual") or {}).get("colors") or [])
    logo_value = (profile.get("visual") or {}).get("logo")
    logo: Path | None = None
    if logo_value:
        candidate = Path(logo_value).expanduser()
        if not candidate.is_absolute():
            candidate = profile_path.parent / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise PipelineError(f"品牌 Logo 文件不存在：{candidate}")
        logo = candidate
    fonts = (profile.get("visual") or {}).get("fonts") or []
    corner_radius = (profile.get("visual") or {}).get("corner_radius") or "medium"
    return colors[:2] or ["#17324D", "#F7F3EC"], logo, fonts, corner_radius


def _produce(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    if shutil.which("magick") is None:
        raise PipelineError("缺少 ImageMagick 的 magick 命令，无法执行本地排版。")
    width, height = _canvas_size(args.resolution)
    manifest = read_json(run_dir / "inputs" / "manifest.json")
    references = [Path(path) for path in manifest["reference_images"]]
    product = Path(manifest["product_image"])
    product_for_composite = product
    base_dir = run_dir / "images" / "base"
    composed_dir = run_dir / "images" / "composed"
    composed_dir.mkdir(parents=True, exist_ok=True)
    online_backgrounds = (
        {}
        if args.offline
        else _online_backgrounds(
            args=args,
            run_dir=run_dir,
            plan=plan,
            product=product,
        )
    )
    visual_qa: dict[str, Any]
    final_status: str
    if args.offline:
        visual_qa = {"pass": True, "status": "offline", "issues": []}
        final_status = "completed"
    else:
        online_backgrounds, visual_qa, final_status = _apply_visual_qa(
            args=args,
            run_dir=run_dir,
            plan=plan,
            product=product,
            backgrounds=online_backgrounds,
        )
    budget = (
        read_json(run_dir / "state" / "request_budget.json")
        if not args.offline
        else {"pages": {}}
    )
    palette, logo, preferred_fonts, corner_radius = _brand_visual(args)
    font_path = _font_path(preferred_fonts)
    page_outputs: list[Path] = []
    for page in plan["pages"]:
        if args.offline:
            background = _offline_background(
                references[(page["index"] - 1) % len(references)],
                base_dir / f"page-{page['index']:02d}.png",
                width=width,
                height=height,
            )
        else:
            background = online_backgrounds[page["index"]]
        attempt = (
            1
            if args.offline
            else int(budget["pages"][str(page["index"])]["attempts"])
        )
        page_outputs.append(
            _compose_page(
                page=page,
                background=background,
                product=product_for_composite,
                output_dir=composed_dir,
                width=width,
                height=height,
                palette=palette,
                attempt=attempt,
                logo=logo,
                font_path=font_path,
                corner_radius=corner_radius,
            )
        )

    expected_dimensions = f"{width}x{height}"
    dimension_checks = {
        path.name: _image_dimensions(path) for path in page_outputs
    }
    local_pass = all(
        value == expected_dimensions for value in dimension_checks.values()
    )
    qa = {
        "pass": local_pass and visual_qa.get("pass") is True,
        "checks": {
            "page_count": len(page_outputs),
            "expected_dimensions": expected_dimensions,
            "dimensions": dimension_checks,
            "text_rendering": "deterministic_svg",
            "real_product_pages": [
                page["index"]
                for page in plan["pages"]
                if page["product_mode"] == "real_composite"
            ],
            "real_product_asset": str(product_for_composite),
            "product_pixels_redrawn": False,
            "unsupported_fact_refs": [],
            "visual_model_review": visual_qa,
        },
        "issues": [],
    }
    if not local_pass:
        qa["issues"].append("一个或多个页面尺寸不符合输出合同。")
        raise PipelineError("本地页面 QA 未通过，详情见 QA 报告。")
    qa["issues"].extend(visual_qa.get("issues", []))

    deliverables = run_dir / "deliverables"
    deliverables.mkdir(parents=True, exist_ok=True)
    for page_spec, page_output in zip(plan["pages"], page_outputs):
        shutil.copy2(
            page_output,
            deliverables / f"page-{page_spec['index']:02d}.png",
        )
    preview = deliverables / "整组预览.png"
    _run_command(
        [
            "magick",
            "montage",
            "-font",
            str(font_path),
            *[str(path) for path in page_outputs],
            "-tile",
            "3x",
            "-geometry",
            "384x512+16+16",
            "-background",
            "#E7E3DC",
            str(preview),
        ],
        label="整组预览生成",
    )
    write_json(deliverables / "图文内容.json", plan)
    write_text(deliverables / "发布文案.md", _render_copy_markdown(plan))
    write_json(deliverables / "QA报告.json", qa)
    if args.offline:
        write_json(
            run_dir / "state" / "request_budget.json",
            {
                "maximum_image_requests": len(plan["pages"]) + 2,
                "used": 0,
                "pages": {},
            },
        )
    summary = {
        "status": final_status,
        "run_dir": str(run_dir),
        "page_count": len(page_outputs),
        "deliverables": str(deliverables),
        "preview": str(preview),
        "qa": str(deliverables / "QA报告.json"),
    }
    write_json(run_dir / "state" / "run_state.json", summary)
    return summary


def prepare_run(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    plan_source = Path(args.plan_file).expanduser().resolve()
    plan = read_json(plan_source)
    validate_plan(plan)
    brand_context = _resolve_brand_context(args, plan)
    output_root = Path(args.output_root).expanduser().resolve()
    run_dir = output_root / args.run_name
    if run_dir.exists() and any(run_dir.iterdir()) and not args.resume:
        raise PipelineError(
            f"运行目录已存在：{run_dir}。请使用 --resume 或更换 --run-name。"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    inputs = run_dir / "inputs"
    references = [
        copy_input(
            Path(value).expanduser().resolve(),
            inputs / f"reference-{index:02d}{Path(value).suffix.lower()}",
        )
        for index, value in enumerate(args.reference_image, 1)
    ]
    if not 1 <= len(references) <= 9:
        raise PipelineError("--reference-image 必须提供 1–9 张。")
    product = copy_input(
        Path(args.product_image).expanduser().resolve(),
        inputs / f"product{Path(args.product_image).suffix.lower()}",
    )
    reference_copy = copy_input(
        Path(args.reference_copy_file).expanduser().resolve(),
        inputs / "reference-copy.txt",
    )
    plan_copy = copy_input(plan_source, inputs / "content-plan.json")
    brand_profile_copy: Path | None = None
    if args.brand_profile_file:
        source = Path(args.brand_profile_file).expanduser().resolve()
        brand_profile_copy = copy_input(source, inputs / "brand-profile.json")
    write_json(
        inputs / "manifest.json",
        {
            "reference_images": [str(path) for path in references],
            "reference_copy": str(reference_copy),
            "product_image": str(product),
            "plan_file": str(plan_copy),
            "brand_profile": str(brand_profile_copy or ""),
            "product_id": args.product_id or "",
        },
    )
    write_json(run_dir / "outputs" / "内容方案.json", plan)
    write_text(run_dir / "outputs" / "内容方案.md", render_plan_markdown(plan))
    if brand_context is not None:
        write_json(run_dir / "outputs" / "品牌任务上下文.json", brand_context)
    return run_dir, plan


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    run_dir, plan = prepare_run(args)
    if not args.approve:
        summary = {
            "status": "awaiting_approval",
            "run_dir": str(run_dir),
            "plan": str(run_dir / "outputs" / "内容方案.md"),
            "page_count": len(plan["pages"]),
            "next_step": "确认内容方案后使用 --approve --resume 继续。",
        }
        write_json(run_dir / "state" / "run_state.json", summary)
        return summary
    return _produce(args=args, run_dir=run_dir, plan=plan)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--reference-image", action="append", required=True)
    parser.add_argument("--reference-copy-file", required=True)
    parser.add_argument("--product-image", required=True)
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--brand-profile-file")
    parser.add_argument("--product-id")
    parser.add_argument("--output-root", default=".brand_ugc")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--visual-qa-file")
    parser.add_argument(
        "--image-generator-script",
        default=str(DEFAULT_IMAGE_GENERATOR),
    )
    return parser.parse_args()


def main() -> int:
    try:
        summary = run_pipeline(parse_args())
    except PipelineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

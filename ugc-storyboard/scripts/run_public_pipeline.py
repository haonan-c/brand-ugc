#!/usr/bin/env python3
"""Run the EvoLink-backed public 15-second ecommerce storyboard workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_CONFIG = SKILL_DIR / "config" / "public_gateway.json"
SCHEMAS = SKILL_DIR / "schemas"
STAGE_REFERENCES = SKILL_DIR / "references" / "stages"

from contracts import ContractError  # noqa: E402
from evolink_client import EvoLinkClient, EvoLinkError  # noqa: E402
from extract_12_frames import extract_frames, make_collage, read_storyboard_json_timepoints  # noqa: E402
from prepare_analysis_media import prepare as prepare_analysis_media  # noqa: E402
from run_public_stage import load_runtime, run_structured_stage  # noqa: E402


def read_text(path: Path | None, default: str = "") -> str:
    if path is None:
        return default
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_brand_profile(
    profile_path: Path,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Resolve one product from a reusable brand profile."""

    profile = read_json(profile_path)
    if not isinstance(profile, dict):
        raise RuntimeError("品牌档案顶层必须是 JSON 对象。")
    products = profile.get("products")
    if not isinstance(products, list):
        raise RuntimeError("品牌档案 products 必须是数组。")
    if product_id:
        product = next(
            (item for item in products if item.get("product_id") == product_id),
            None,
        )
        if product is None:
            raise RuntimeError(f"品牌档案中不存在产品：{product_id}")
    elif len(products) == 1:
        product = products[0]
    else:
        raise RuntimeError("品牌档案包含多个产品时必须提供 --brand-product-id。")
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


def build_product_context(
    task_product_info: str,
    brand_context: dict[str, Any] | None,
) -> str:
    """Place task-specific facts before optional reusable brand constraints."""

    if brand_context is None:
        return task_product_info
    return (
        task_product_info.strip()
        + "\n\n【可复用品牌档案】\n"
        + "以下档案低于本次任务明确指令，但其中禁用表达与事实边界必须遵守。\n"
        + json.dumps(brand_context, ensure_ascii=False, indent=2)
    ).strip()


def check_runtime_dependencies() -> None:
    missing = [
        command
        for command in ("ffmpeg", "ffprobe")
        if shutil.which(command) is None
    ]
    if missing:
        raise RuntimeError(
            "缺少运行依赖："
            + "、".join(missing)
            + "。请先安装 FFmpeg，并确认这些命令可从 PATH 运行。"
        )


def preview_text(path: Path, max_chars: int = 1200) -> str:
    text = read_text(path).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...\n[内容较长，已截取预览，完整内容见文件]"


def prepare_run_directory(run_dir: Path, *, resume: bool) -> Path:
    """Create a new run or require explicit resume for a non-empty run."""

    if run_dir.exists() and any(run_dir.iterdir()) and not resume:
        raise RuntimeError(
            f"运行目录已存在：{run_dir}。为避免重复计费，请使用 --resume，"
            "或更换 --run-name。"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def copy_input(path: Path | None, target_dir: Path) -> Path | None:
    if path is None:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        if _digest(target) != _digest(path):
            raise RuntimeError(
                f"恢复运行时输入文件发生变化：{path.name}。请更换 --run-name。"
            )
        return target
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    return target


class Progress:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.items: list[dict[str, Any]] = read_json(run_dir / "progress.json", [])

    def add(self, stage: str, status: str, outputs: dict[str, str] | None = None) -> None:
        item = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "status": status,
            "outputs": outputs or {},
        }
        self.items.append(item)
        write_json(self.run_dir / "progress.json", self.items)
        with (self.run_dir / "progress.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        lines = [
            f"{entry['time']} | {entry['stage']} | {entry['status']}"
            for entry in self.items
        ]
        write_text(self.run_dir / "进度.txt", "\n".join(lines) + "\n")
        print(f"\n[{stage}] {status}", flush=True)
        for key, value in (outputs or {}).items():
            if key != "video_prompt_text":
                print(f"- {key}: {value}", flush=True)

    def skip(self, stage: str) -> None:
        print(f"\n[{stage}] 已完成，--resume 跳过", flush=True)


class StageState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = read_json(path, {"stages": {}})

    def complete(self, stage: str, outputs: list[Path]) -> bool:
        entry = self.data["stages"].get(stage, {})
        return entry.get("status") == "completed" and all(path.exists() for path in outputs)

    def mark(self, stage: str, status: str, outputs: list[Path] | None = None) -> None:
        self.data["stages"][stage] = {
            "status": status,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "outputs": [str(path.resolve()) for path in (outputs or [])],
        }
        write_json(self.path, self.data)


class RequestBudget:
    def __init__(self, path: Path, maximum: int) -> None:
        self.path = path
        self.maximum = maximum
        self.data: dict[str, Any] = read_json(
            path,
            {"maximum": maximum, "used": 0, "requests": []},
        )
        self.data["maximum"] = maximum

    def consume(self, label: str) -> None:
        if int(self.data["used"]) >= self.maximum:
            raise RuntimeError(
                f"本次运行已达到 {self.maximum} 次模型业务请求上限；"
                "已停止，避免继续计费。"
            )
        self.data["used"] = int(self.data["used"]) + 1
        self.data["requests"].append(
            {"label": label, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        )
        write_json(self.path, self.data)

    def summary(self) -> dict[str, Any]:
        return {
            "maximum": self.maximum,
            "used": int(self.data["used"]),
            "requests": list(self.data["requests"]),
        }


def _credits_available(response: dict[str, Any]) -> bool:
    token = ((response.get("data") or {}).get("token") or {})
    return bool(token.get("unlimited_credits")) or float(token.get("remaining_credits", 0)) > 0


def _context_prompt(reference_name: str, **contexts: Any) -> str:
    parts = [read_text(STAGE_REFERENCES / reference_name).strip()]
    for label, value in contexts.items():
        rendered = (
            json.dumps(value, ensure_ascii=False, indent=2)
            if not isinstance(value, str)
            else value.strip()
        )
        parts.extend(["", f"【{label}】", rendered or "未上传/空"])
    return "\n".join(parts).strip()


def _compact_image_prompt(
    reference_name: str,
    shot_prompts: dict[str, Any],
    *,
    role_note: str,
) -> str:
    lock = shot_prompts["series_lock"]
    lines = [
        read_text(STAGE_REFERENCES / reference_name).strip(),
        "",
        f"参考图角色：{role_note}",
        "系列锁："
        f"产品={lock['product'][:100]}；人物={lock['person'][:100]}；"
        f"环境={lock['environment'][:80]}；光线={lock['lighting'][:60]}；"
        f"色调={lock['color_grade'][:60]}。",
        "逐格要求：",
    ]
    for shot in shot_prompts["shots"]:
        lines.append(
            f"{shot['index']:02d}｜{shot['image_prompt'][:65]}｜"
            f"禁止：{shot['negative_prompt'][:25]}"
        )
    return "\n".join(lines)


def _task_has_id(path: Path) -> bool:
    return bool((read_json(path, {}) or {}).get("task_id"))


def _run_image_with_qa(
    *,
    client: EvoLinkClient,
    budget: RequestBudget,
    stage_key: str,
    prompt: str,
    qa_reference_name: str,
    reference_images: list[Path],
    qa_media: list[Path],
    images_dir: Path,
    state_dir: Path,
    qa_dir: Path,
    resolution: str,
    poll_interval: float,
    poll_timeout: float,
) -> tuple[Path, dict[str, Any]]:
    last_qa: dict[str, Any] | None = None
    for attempt in range(2):
        suffix = "" if attempt == 0 else "_retry"
        output_dir = images_dir / f"{stage_key}{suffix}"
        output = output_dir / "image-01.png"
        task_state = state_dir / f"{stage_key}{suffix}.task.json"
        qa_json = qa_dir / f"{stage_key}_QA_{attempt + 1}.json"
        qa_trace = qa_dir / f"{stage_key}_QA_{attempt + 1}.raw.json"
        if output.exists() and qa_json.exists():
            last_qa = read_json(qa_json)
            if last_qa.get("pass") is True:
                return output.resolve(), last_qa
            if attempt == 1:
                raise RuntimeError(
                    f"{stage_key} 纠错生成后仍未通过视觉 QA。"
                    f"失败图片和报告已保存：{output}，{qa_json}"
                )
            continue
        reference_urls: list[str] | None = None
        if not _task_has_id(task_state):
            reference_urls = [
                client.upload_image(path)[0]
                for path in reference_images
            ]
            budget.consume(f"{stage_key}{suffix}_generation")
        image_prompt = prompt
        if last_qa:
            image_prompt += (
                "\n\n【仅纠正以下 QA 问题，其他已正确内容保持不变】\n"
                + (last_qa.get("correction_prompt") or json.dumps(
                    last_qa.get("issues", []),
                    ensure_ascii=False,
                ))
            )
        generated = client.generate_image(
            prompt=image_prompt,
            reference_images=[],
            reference_urls=reference_urls,
            output_path=output,
            state_path=task_state,
            quality=resolution,
            aspect_ratio="9:16",
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            request_id=f"{stage_key}{suffix}",
        )

        qa_prompt = _context_prompt(
            qa_reference_name,
            QA任务=(
                "审查随请求提供的第一张生成图。输出严格 JSON。"
                "模板图阶段的 product_consistency 表示产品清除是否正确；"
                "最终图阶段表示产品外观是否与参考图一致。"
                "pass 只有在所有关键检查为 true 且无 major/critical 问题时才为 true。"
            ),
        )
        last_qa = run_structured_stage(
            client=client,
            stage_name=f"{stage_key}_qa_{attempt + 1}",
            prompt=qa_prompt,
            media_files=[generated, *qa_media],
            schema_path=SCHEMAS / "image_qa.schema.json",
            json_output=qa_json,
            text_output=None,
            trace_output=qa_trace,
            renderer=None,
            timeline=False,
            consume_request=budget.consume,
        )
        if last_qa["pass"]:
            return generated, last_qa
        if attempt == 1:
            raise RuntimeError(
                f"{stage_key} 纠错生成后仍未通过视觉 QA。"
                f"失败图片和报告已保存：{generated}，{qa_json}"
            )
    raise RuntimeError(f"{stage_key} 图片阶段异常结束")


def _stage_outputs(run_dir: Path) -> dict[str, Path]:
    return {
        "analysis_json": run_dir / "outputs" / "12镜头解析.json",
        "analysis_md": run_dir / "outputs" / "12镜头解析.md",
        "collage": run_dir / "collages" / "12宫格参考图.jpg",
        "new_script_json": run_dir / "outputs" / "新产品-12分镜脚本.json",
        "new_script_md": run_dir / "outputs" / "新产品-12分镜脚本.md",
        "shot_prompts_json": run_dir / "outputs" / "1-12分镜提示词.json",
        "shot_prompts_md": run_dir / "outputs" / "1-12分镜提示词.md",
        "video_prompt_json": run_dir / "outputs" / "视频提示词1-12.json",
        "video_prompt_txt": run_dir / "outputs" / "视频提示词1-12.txt",
    }


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    video_source = Path(args.video).expanduser().resolve()
    product_source = Path(args.product_image).expanduser().resolve()
    person_source = Path(args.person_image).expanduser().resolve() if args.person_image else None
    copy_source = Path(args.copy_file).expanduser().resolve() if args.copy_file else None
    brand_profile_value = getattr(args, "brand_profile_file", None)
    brand_profile_source = (
        Path(brand_profile_value).expanduser().resolve()
        if brand_profile_value
        else None
    )
    for required in (video_source, product_source):
        if not required.is_file():
            raise RuntimeError(f"输入文件不存在：{required}")
    for optional in (person_source, copy_source, brand_profile_source):
        if optional is not None and not optional.is_file():
            raise RuntimeError(f"输入文件不存在：{optional}")

    check_runtime_dependencies()

    resolution = args.resolution.upper()
    if resolution not in {"1K", "2K"}:
        raise RuntimeError("--resolution 仅允许 1K 或 2K；默认 2K，不自动降级。")
    if resolution == "1K":
        print("警告：已显式选择 1K；默认质量标准为 2K。", file=sys.stderr)

    output_root = Path(args.output_root).expanduser().resolve()
    run_dir = output_root / args.run_name
    if run_dir.exists() and any(run_dir.iterdir()):
        prepare_run_directory(run_dir, resume=args.resume)

    config, client = load_runtime(args.config)
    credits = client.get_credits()
    if not _credits_available(credits):
        raise RuntimeError("EvoLink 可用余额为 0，请充值后再运行。")
    prepare_run_directory(run_dir, resume=args.resume)

    dirs = {
        name: run_dir / name
        for name in (
            "inputs",
            "outputs",
            "frames",
            "collages",
            "images",
            "prompts",
            "logs",
            "qa",
            "state",
            "media",
            "deliverables",
        )
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    video = copy_input(video_source, dirs["inputs"])
    product_image = copy_input(product_source, dirs["inputs"])
    person_image = copy_input(person_source, dirs["inputs"])
    copy_file = copy_input(copy_source, dirs["inputs"])
    brand_profile_file = copy_input(
        brand_profile_source,
        dirs["inputs"] / "brand-profile",
    )
    assert video is not None and product_image is not None

    brand_context = (
        resolve_brand_profile(
            brand_profile_file,
            getattr(args, "brand_product_id", None),
        )
        if brand_profile_file
        else None
    )
    if brand_context is not None:
        write_json(dirs["inputs"] / "品牌任务上下文.json", brand_context)

    product_info = args.product_info
    if args.product_info_file:
        product_info = read_text(Path(args.product_info_file).expanduser().resolve())
    if not product_info.strip():
        product_info = f"产品名称：{product_image.stem}\n产品备注：需要确认。"
    product_info = build_product_context(product_info, brand_context)
    product_info_path = dirs["inputs"] / "产品信息.txt"
    if not product_info_path.exists():
        write_text(product_info_path, product_info.strip() + "\n")

    person_note = (
        "已提供人物参考图：锁定脸型、发型、服装与体态；不推断敏感属性。"
        if person_image
        else "未提供人物参考图：不得复制对标真人；必要时使用非真实虚构演员。"
    )
    person_note_path = dirs["inputs"] / "人物图说明.txt"
    if not person_note_path.exists():
        write_text(person_note_path, person_note + "\n")
    copy_text = read_text(copy_file).strip() if copy_file else "未上传/空"
    if not copy_file:
        write_text(dirs["inputs"] / "文案.txt", copy_text + "\n")

    progress = Progress(run_dir)
    state = StageState(dirs["state"] / "stage_state.json")
    budget = RequestBudget(
        dirs["state"] / "request_budget.json",
        int(config["limits"].get("max_model_requests", 14)),
    )
    outputs = _stage_outputs(run_dir)
    if not progress.items:
        progress.add(
            "开始",
            "已创建运行文件夹",
            {
                "run_dir": str(run_dir),
                "video": str(video),
                "product_image": str(product_image),
                "person_image": str(person_image or ""),
                "copy_file": str(copy_file or ""),
                "brand_profile_file": str(brand_profile_file or ""),
            },
        )

    # 1. 视频解析：只发送本地派生代理和音轨。
    if state.complete("analysis", [outputs["analysis_json"], outputs["analysis_md"]]):
        progress.skip("视频解析完成")
        analysis = read_json(outputs["analysis_json"])
    else:
        state.mark("analysis", "running")
        proxy = dirs["media"] / "analysis_proxy.mp4"
        audio = dirs["media"] / "analysis_audio.m4a"
        media_manifest = dirs["outputs"] / "analysis_media_manifest.json"
        if not proxy.exists() or not media_manifest.exists():
            manifest = prepare_analysis_media(video, proxy, audio)
            write_json(media_manifest, manifest)
        else:
            manifest = read_json(media_manifest)
        analysis_media = [proxy]
        if manifest.get("audio") and audio.exists():
            analysis_media.append(audio)
        analysis = run_structured_stage(
            client=client,
            stage_name="analysis",
            prompt=_context_prompt(
                "01-video-analysis.md",
                输入说明=(
                    "第一份媒体是无声分析代理视频；如有第二份媒体，则为单声道音轨。"
                    "原始视频未上传。"
                ),
            ),
            media_files=analysis_media,
            schema_path=SCHEMAS / "analysis.schema.json",
            json_output=outputs["analysis_json"],
            text_output=outputs["analysis_md"],
            trace_output=dirs["outputs"] / "12镜头解析.raw.json",
            renderer="analysis",
            timeline=True,
            consume_request=budget.consume,
        )
        state.mark("analysis", "completed", [outputs["analysis_json"], outputs["analysis_md"]])
        progress.add("视频解析完成", "完成", {"output": str(outputs["analysis_md"])})

    # 2. 本地原片抽帧。
    if state.complete("collage", [outputs["collage"]]):
        progress.skip("12宫格参考图完成")
    else:
        state.mark("collage", "running")
        points = read_storyboard_json_timepoints(outputs["analysis_json"])
        frames = extract_frames(video, points, dirs["frames"])
        collage = make_collage(dirs["frames"], outputs["collage"])
        write_json(
            dirs["outputs"] / "local_frames_manifest.json",
            {
                "video_file": video.name,
                "timepoints_seconds": [round(item, 3) for item in points],
                "frames": frames,
                "frame_count": 12,
                "collage": str(collage.resolve()),
                "collage_layout": {"columns": 3, "rows": 4, "panels": 12},
            },
        )
        state.mark("collage", "completed", [outputs["collage"]])
        progress.add("12宫格参考图完成", "完成", {"collage": str(outputs["collage"])})

    # 3. 新产品脚本。
    if state.complete(
        "new_script",
        [outputs["new_script_json"], outputs["new_script_md"]],
    ):
        progress.skip("新分镜脚本完成")
        new_script = read_json(outputs["new_script_json"])
    else:
        state.mark("new_script", "running")
        media = [product_image] + ([person_image] if person_image else [])
        new_script = run_structured_stage(
            client=client,
            stage_name="new_script",
            prompt=_context_prompt(
                "02-new-product-script.md",
                原视频解析JSON=analysis,
                产品信息=read_text(product_info_path),
                人物图说明=read_text(person_note_path),
                图片顺序="图片1为产品图；如有图片2，则为人物参考图。",
            ),
            media_files=media,
            schema_path=SCHEMAS / "new_script.schema.json",
            json_output=outputs["new_script_json"],
            text_output=outputs["new_script_md"],
            trace_output=dirs["outputs"] / "新产品-12分镜脚本.raw.json",
            renderer="new_script",
            timeline=True,
            consume_request=budget.consume,
        )
        state.mark(
            "new_script",
            "completed",
            [outputs["new_script_json"], outputs["new_script_md"]],
        )
        progress.add("新分镜脚本完成", "完成", {"output": str(outputs["new_script_md"])})

    # 4. 十二分镜提示词。
    if state.complete(
        "shot_prompts",
        [outputs["shot_prompts_json"], outputs["shot_prompts_md"]],
    ):
        progress.skip("12分镜提示词完成")
        shot_prompts = read_json(outputs["shot_prompts_json"])
    else:
        state.mark("shot_prompts", "running")
        shot_prompts = run_structured_stage(
            client=client,
            stage_name="shot_prompts",
            prompt=_context_prompt(
                "03-shot-prompts.md",
                新产品脚本JSON=new_script,
                参考图说明="随请求图片为原视频本地抽取的3列×4行十二宫格。",
            ),
            media_files=[outputs["collage"]],
            schema_path=SCHEMAS / "shot_prompts.schema.json",
            json_output=outputs["shot_prompts_json"],
            text_output=outputs["shot_prompts_md"],
            trace_output=dirs["outputs"] / "1-12分镜提示词.raw.json",
            renderer="shot_prompts",
            timeline=True,
            consume_request=budget.consume,
        )
        state.mark(
            "shot_prompts",
            "completed",
            [outputs["shot_prompts_json"], outputs["shot_prompts_md"]],
        )
        progress.add("12分镜提示词完成", "完成", {"output": str(outputs["shot_prompts_md"])})

    api = config["api"]
    poll_interval = float(api.get("poll_interval_seconds", 3))
    poll_timeout = float(api.get("poll_timeout_seconds", 600))

    # 5. 模板图 + QA + 最多一次纠错。
    template_state = state.data["stages"].get("template_image", {})
    template_path = Path(template_state["outputs"][0]) if template_state.get("outputs") else None
    if template_path and state.complete("template_image", [template_path]):
        progress.skip("第一步模板图完成")
        template_image = template_path
        template_qa = read_json(dirs["qa"] / "template_image_QA_final.json", {})
    else:
        state.mark("template_image", "running")
        template_prompt = _compact_image_prompt(
            "04-template-image.md",
            shot_prompts,
            role_note="参考图1=原视频十二宫格；如有参考图2=人物图。",
        )
        write_text(dirs["prompts"] / "第一步模板图.prompt.txt", template_prompt)
        template_refs = [outputs["collage"]] + ([person_image] if person_image else [])
        template_image, template_qa = _run_image_with_qa(
            client=client,
            budget=budget,
            stage_key="step1_template",
            prompt=template_prompt,
            qa_reference_name="04-template-image.md",
            reference_images=template_refs,
            qa_media=template_refs,
            images_dir=dirs["images"],
            state_dir=dirs["state"],
            qa_dir=dirs["qa"],
            resolution=resolution,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
        write_json(dirs["qa"] / "template_image_QA_final.json", template_qa)
        state.mark("template_image", "completed", [template_image])
        progress.add(
            "第一步模板图完成",
            f"完成（{resolution}）",
            {"image": str(template_image)},
        )

    # 6. 最终图 + QA + 最多一次纠错。
    final_state = state.data["stages"].get("final_image", {})
    final_path = Path(final_state["outputs"][0]) if final_state.get("outputs") else None
    if final_path and state.complete("final_image", [final_path]):
        progress.skip("最终分镜图完成")
        final_image = final_path
        final_qa = read_json(dirs["qa"] / "final_image_QA_final.json", {})
    else:
        state.mark("final_image", "running")
        final_prompt = _compact_image_prompt(
            "05-final-image.md",
            shot_prompts,
            role_note=(
                "参考图1=已通过QA的模板十二宫格；参考图2=产品图；"
                "如有参考图3=人物图。"
            ),
        )
        write_text(dirs["prompts"] / "最终分镜图.prompt.txt", final_prompt)
        final_refs = [template_image, product_image] + ([person_image] if person_image else [])
        final_image, final_qa = _run_image_with_qa(
            client=client,
            budget=budget,
            stage_key="final_storyboard",
            prompt=final_prompt,
            qa_reference_name="05-final-image.md",
            reference_images=final_refs,
            qa_media=[product_image] + ([person_image] if person_image else []),
            images_dir=dirs["images"],
            state_dir=dirs["state"],
            qa_dir=dirs["qa"],
            resolution=resolution,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
        write_json(dirs["qa"] / "final_image_QA_final.json", final_qa)
        state.mark("final_image", "completed", [final_image])
        progress.add(
            "最终分镜图完成",
            f"完成（{resolution}）",
            {"image": str(final_image)},
        )

    # 7. Seedance 总提示词 + 12 条运动指令。
    if state.complete(
        "video_prompt",
        [outputs["video_prompt_json"], outputs["video_prompt_txt"]],
    ):
        progress.skip("视频提示词完成")
        video_prompt_payload = read_json(outputs["video_prompt_json"])
    else:
        state.mark("video_prompt", "running")
        video_media = [final_image, product_image] + ([person_image] if person_image else [])
        video_prompt_payload = run_structured_stage(
            client=client,
            stage_name="video_prompt",
            prompt=_context_prompt(
                "06-video-prompt.md",
                十二分镜提示词JSON=shot_prompts,
                用户文案=copy_text,
                品牌任务上下文=brand_context or "未提供",
                图片顺序=(
                    "图片1为最终十二宫格，图片2为产品图；"
                    "如有图片3，则为人物参考图。"
                ),
            ),
            media_files=video_media,
            schema_path=SCHEMAS / "video_prompt.schema.json",
            json_output=outputs["video_prompt_json"],
            text_output=outputs["video_prompt_txt"],
            trace_output=dirs["outputs"] / "视频提示词1-12.raw.json",
            renderer="video_prompt",
            timeline=True,
            consume_request=budget.consume,
        )
        state.mark(
            "video_prompt",
            "completed",
            [outputs["video_prompt_json"], outputs["video_prompt_txt"]],
        )
        progress.add(
            "视频提示词完成",
            "完成",
            {
                "final_image": str(final_image),
                "video_prompt_text": video_prompt_payload["master_prompt"].strip(),
            },
        )

    master_prompt_text = video_prompt_payload["master_prompt"].strip()
    deliverable_paths = {
        "final_storyboard": dirs["deliverables"] / "最终12宫格分镜图.png",
        "video_prompt": dirs["deliverables"] / "视频提示词1-12.txt",
        "qa_report": dirs["deliverables"] / "QA报告.json",
    }
    report = {
        "run_dir": str(run_dir),
        "provider": "EvoLink",
        "models": config["models"],
        "requested_resolution": resolution,
        "analysis": str(outputs["analysis_md"]),
        "collage": str(outputs["collage"]),
        "new_script": str(outputs["new_script_md"]),
        "shot_prompts": str(outputs["shot_prompts_md"]),
        "template_image": str(template_image),
        "template_qa": template_qa,
        "final_image": str(final_image),
        "final_qa": final_qa,
        "video_prompt": str(outputs["video_prompt_txt"]),
        "brand_context": str(
            (dirs["inputs"] / "品牌任务上下文.json")
            if brand_context is not None
            else ""
        ),
        "deliverables": {
            name: str(path) for name, path in deliverable_paths.items()
        },
        "request_budget": budget.summary(),
        "conversation_output": {
            "final_image": str(deliverable_paths["final_storyboard"]),
            "video_prompt_text": master_prompt_text,
        },
    }
    write_json(dirs["qa"] / "QA报告.json", report)
    write_json(run_dir / "stage_summary.json", report)

    deliverable_sources = {
        final_image: deliverable_paths["final_storyboard"],
        outputs["video_prompt_txt"]: deliverable_paths["video_prompt"],
        dirs["qa"] / "QA报告.json": deliverable_paths["qa_report"],
    }
    deliverable_outputs = list(deliverable_sources.values())
    if state.complete("deliverables", deliverable_outputs):
        progress.skip("交付物汇总完成")
    else:
        state.mark("deliverables", "running")
        for source, target in deliverable_sources.items():
            shutil.copy2(source, target)
        state.mark("deliverables", "completed", deliverable_outputs)
        progress.add(
            "交付物汇总完成",
            "完成",
            {"directory": str(dirs["deliverables"])},
        )

    print("\n=== 流程结果预览 ===")
    print(f"\n[1] 视频解析完成\n文件: {outputs['analysis_md']}\n{preview_text(outputs['analysis_md'])}")
    print(f"\n[2] 12宫格参考图完成\n图片: {outputs['collage']}")
    print(f"\n[3] 新分镜脚本完成\n文件: {outputs['new_script_md']}\n{preview_text(outputs['new_script_md'])}")
    print(f"\n[4] 12分镜提示词完成\n文件: {outputs['shot_prompts_md']}\n{preview_text(outputs['shot_prompts_md'])}")
    print(f"\n[5] 第一步模板图完成\n图片: {template_image}")
    print(f"\n[6] 最终分镜图完成\n图片: {final_image}")
    print(f"\n[7] 视频提示词完成\n文件: {outputs['video_prompt_txt']}")
    print("\n=== 对话框输出 ===")
    print(f"最终12宫格分镜图: {deliverable_paths['final_storyboard']}")
    print("\n视频提示词:")
    print(master_prompt_text)
    print(f"\n12条详细运动指令已保存：{deliverable_paths['video_prompt']}")
    print("\n=== 结构化摘要 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--product-image", required=True)
    parser.add_argument("--person-image")
    parser.add_argument("--copy-file")
    parser.add_argument("--product-info", default="")
    parser.add_argument("--product-info-file")
    parser.add_argument("--brand-profile-file")
    parser.add_argument("--brand-product-id")
    parser.add_argument("--config", default=str(DEFAULT_PUBLIC_CONFIG))
    parser.add_argument("--output-root", default=".brand_ugc")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        run_pipeline(parse_args())
    except (RuntimeError, EvoLinkError, ContractError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

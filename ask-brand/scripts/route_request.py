#!/usr/bin/env python3
"""Diagnose a brand marketing request and recommend one downstream skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


IMAGE_TERMS = {
    "图文",
    "图片",
    "小红书",
    "笔记",
    "封面",
    "内页",
    "image post",
    "carousel",
}
VIDEO_TERMS = {"视频", "短视频", "分镜", "seedance", "storyboard", "video"}
PROFILE_TERMS = {"品牌档案", "品牌规范", "品牌语气", "brand profile", "brand kit"}


def _contains(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _existing_files(values: list[str]) -> list[str]:
    return [
        str(Path(value).expanduser().resolve())
        for value in values
        if Path(value).expanduser().is_file()
    ]


def _missing_for_image(args: argparse.Namespace) -> list[str]:
    missing = []
    if not _existing_files(args.reference_image):
        missing.append("对标图片")
    if not args.reference_copy_file or not Path(
        args.reference_copy_file
    ).expanduser().is_file():
        missing.append("对标文案")
    if not args.product_image or not Path(args.product_image).expanduser().is_file():
        missing.append("产品图")
    return missing


def _missing_for_video(args: argparse.Namespace) -> list[str]:
    missing = []
    if not args.reference_video or not Path(
        args.reference_video
    ).expanduser().is_file():
        missing.append("对标视频")
    if not args.product_image or not Path(args.product_image).expanduser().is_file():
        missing.append("产品图")
    return missing


def _decision(
    *,
    status: str,
    intent: str,
    skill: str,
    reason: str,
    missing: list[str] | None = None,
    question: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": status,
        "intent": intent,
        "recommended_skill": skill,
        "reason": reason,
        "missing_inputs": missing or [],
        "question": question,
    }


def route(args: argparse.Namespace) -> dict[str, Any]:
    request = args.request.strip()
    wants_image = _contains(request, IMAGE_TERMS)
    wants_video = _contains(request, VIDEO_TERMS)
    wants_profile = _contains(request, PROFILE_TERMS)

    if wants_image and wants_video:
        return _decision(
            status="needs_confirmation",
            intent="multi_format",
            skill="",
            reason="请求同时明确提到图文和视频，不默认同时生成两种内容。",
            question="这次希望先生成图文，还是先生成短视频？",
        )
    if wants_image:
        missing = _missing_for_image(args)
        return _decision(
            status="needs_input" if missing else "ready",
            intent="image_post",
            skill="ugc-image-post",
            reason="用户明确要求图文、小红书笔记或图片组。",
            missing=missing,
            question=(
                "请补充" + "、".join(missing) + "后继续图文生产。"
                if missing
                else ""
            ),
        )
    if wants_video:
        missing = _missing_for_video(args)
        return _decision(
            status="needs_input" if missing else "ready",
            intent="short_video",
            skill="ugc-storyboard",
            reason="用户明确要求短视频、分镜或 Seedance 提示词。",
            missing=missing,
            question=(
                "请补充" + "、".join(missing) + "后继续短视频生产。"
                if missing
                else ""
            ),
        )
    if wants_profile:
        return _decision(
            status="ready",
            intent="brand_profile",
            skill="brand-profile",
            reason="用户明确要求创建或维护品牌档案。",
        )

    image_ready = not _missing_for_image(args)
    video_ready = not _missing_for_video(args)
    if image_ready and video_ready:
        return _decision(
            status="needs_confirmation",
            intent="ambiguous_content",
            skill="ugc-image-post",
            reason="当前素材同时满足图文和短视频路径，推荐先用成本较低的图文验证表达。",
            question="当前素材同时支持两条路径，是否先生成图文候选稿？",
        )
    if image_ready:
        return _decision(
            status="ready",
            intent="image_post",
            skill="ugc-image-post",
            reason="现有素材满足对标图文、对标文案和产品图合同。",
        )
    if video_ready:
        return _decision(
            status="ready",
            intent="short_video",
            skill="ugc-storyboard",
            reason="现有素材满足对标视频和产品图合同。",
        )
    return _decision(
        status="needs_confirmation",
        intent="unknown",
        skill="",
        reason="请求未明确内容形式，现有素材也不足以唯一判断路径。",
        question="本次希望先生成图文内容，还是短视频内容？",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--reference-image", action="append", default=[])
    parser.add_argument("--reference-copy-file")
    parser.add_argument("--reference-video")
    parser.add_argument("--product-image")
    parser.add_argument("--brand-profile-file")
    return parser.parse_args()


def main() -> int:
    decision = route(parse_args())
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

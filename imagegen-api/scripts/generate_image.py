#!/usr/bin/env python3
"""Generate an image through EvoLink Nano Banana Pro."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SECRET_FILE = SKILL_DIR / "secrets" / "api_key.txt"


def _load_adapter():
    candidates = [
        SKILL_DIR.parent / "brand-ugc" / "scripts",
        Path.home() / ".codex" / "skills" / "brand-ugc" / "scripts",
    ]
    for candidate in candidates:
        if (candidate / "evolink_client.py").exists():
            sys.path.insert(0, str(candidate))
            from evolink_client import EvoLinkClient, EvoLinkError, limit_image_prompt

            return EvoLinkClient, EvoLinkError, limit_image_prompt
    raise SystemExit(
        "缺少 EvoLink 适配器。请同时安装 brand-ugc skill。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="nanobanana")
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--output-dir", default="generated-images")
    parser.add_argument("--aspect-ratio", default="1:1")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--endpoint", default="https://api.evolink.ai")
    parser.add_argument("--image-url", action="append", default=[])
    parser.add_argument("--image-file", action="append", default=[])
    parser.add_argument("--osskey", action="append", default=[])
    parser.add_argument("--api-key")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        path = Path(args.prompt_file).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"提示词文件不存在：{path}")
        prompt = path.read_text(encoding="utf-8-sig").strip()
    else:
        prompt = (args.prompt or "").strip()
    if not prompt:
        raise SystemExit("请使用 --prompt 或 --prompt-file 提供提示词。")
    return prompt


def load_key(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for name in ("EVOLINK_API_KEY", "IMAGEGEN_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if SECRET_FILE.exists():
        value = SECRET_FILE.read_text(encoding="utf-8-sig").strip()
        if value:
            return value
    raise SystemExit(
        f"缺少 EvoLink API Key。请设置 EVOLINK_API_KEY，或写入 {SECRET_FILE}。"
    )


def normalized_endpoint(value: str) -> str:
    endpoint = value.rstrip("/")
    for suffix in ("/v1/images/generations", "/v1/chat/completions"):
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
    return endpoint


def main() -> int:
    args = parse_args()
    provider = args.provider.lower().replace("_", "-")
    if provider not in {"nanobanana", "nano-banana", "banana"}:
        raise SystemExit("EvoLink 版本仅支持 --provider nanobanana。")
    if args.model != "gemini-3-pro-image-preview":
        raise SystemExit("当前流程固定使用 gemini-3-pro-image-preview。")
    if args.osskey:
        raise SystemExit("EvoLink 不支持旧 --osskey；请使用 --image-file 或 --image-url。")
    resolution = args.resolution.upper()
    if resolution not in {"1K", "2K"}:
        raise SystemExit("--resolution 仅允许 1K 或 2K；不会自动降级。")

    EvoLinkClient, EvoLinkError, limit_image_prompt = _load_adapter()
    prompt = limit_image_prompt(load_prompt(args))
    payload = {
        "model": "gemini-3-pro-image-preview",
        "prompt": prompt,
        "size": args.aspect_ratio,
        "quality": resolution,
    }
    if args.image_url:
        payload["image_urls"] = args.image_url
    if args.image_file:
        payload["local_reference_files"] = [
            Path(path).name for path in args.image_file
        ]
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    output_dir = Path(args.output_dir).expanduser().resolve()
    output = output_dir / "image-01.png"
    state = output_dir / "task.json"
    client = EvoLinkClient(
        api_key=load_key(args.api_key),
        api_base_url=normalized_endpoint(args.endpoint),
        image_model="gemini-3-pro-image-preview",
        timeout=args.timeout,
    )
    try:
        image = client.generate_image(
            prompt=prompt,
            reference_images=args.image_file,
            reference_urls=args.image_url,
            output_path=output,
            state_path=state,
            quality=resolution,
            aspect_ratio=args.aspect_ratio,
            poll_timeout=args.timeout,
            request_id=f"imagegen-{output_dir.name}",
        )
    except EvoLinkError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = {
        "provider": "EvoLink / nanobanana",
        "model": "gemini-3-pro-image-preview",
        "output_dir": str(output_dir),
        "task_state": str(state),
        "images": [str(image)],
        "resolution": resolution,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

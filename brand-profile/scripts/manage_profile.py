#!/usr/bin/env python3
"""Create, read, and resolve local brand profiles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


BRAND_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProfileError(ValueError):
    """Raised when a brand profile violates the public contract."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"无法读取品牌档案：{path}") from exc
    if not isinstance(payload, dict):
        raise ProfileError("品牌档案顶层必须是 JSON 对象。")
    return payload


def validate_profile(payload: dict[str, Any]) -> None:
    required = {"schema_version", "brand_id", "brand_name", "products"}
    missing = sorted(required - set(payload))
    if missing:
        raise ProfileError(f"品牌档案缺少必填字段：{missing[0]}")
    if payload["schema_version"] != 1:
        raise ProfileError("schema_version 当前只支持 1。")
    brand_id = payload["brand_id"]
    if not isinstance(brand_id, str) or not BRAND_ID_RE.fullmatch(brand_id):
        raise ProfileError("brand_id 必须使用小写字母、数字和连字符。")
    if not isinstance(payload["brand_name"], str) or not payload["brand_name"].strip():
        raise ProfileError("brand_name 不能为空。")
    if not isinstance(payload["products"], list):
        raise ProfileError("products 必须是数组。")
    seen_products: set[str] = set()
    for index, product in enumerate(payload["products"]):
        if not isinstance(product, dict):
            raise ProfileError(f"products[{index}] 必须是对象。")
        product_id = product.get("product_id")
        if not isinstance(product_id, str) or not BRAND_ID_RE.fullmatch(product_id):
            raise ProfileError(
                f"products[{index}].product_id 必须使用小写字母、数字和连字符。"
            )
        if product_id in seen_products:
            raise ProfileError(f"products 中存在重复 product_id：{product_id}")
        seen_products.add(product_id)
        if not isinstance(product.get("name"), str) or not product["name"].strip():
            raise ProfileError(f"products[{index}].name 不能为空。")
        claims = product.get("verified_claims", [])
        if not isinstance(claims, list):
            raise ProfileError(f"products[{index}].verified_claims 必须是数组。")
        for claim_index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                raise ProfileError(
                    f"products[{index}].verified_claims[{claim_index}] 必须是对象。"
                )
            for field in ("claim", "evidence"):
                if not isinstance(claim.get(field), str) or not claim[field].strip():
                    raise ProfileError(
                        f"products[{index}].verified_claims[{claim_index}].{field} "
                        "不能为空。"
                    )


def profile_path(output_root: Path, brand_id: str) -> Path:
    if not BRAND_ID_RE.fullmatch(brand_id):
        raise ProfileError("brand_id 必须使用小写字母、数字和连字符。")
    return output_root / "brands" / brand_id / "profile.json"


def save_profile(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(Path(args.profile_file).expanduser().resolve())
    validate_profile(payload)
    target = profile_path(
        Path(args.output_root).expanduser().resolve(),
        payload["brand_id"],
    )
    if target.exists() and not args.replace:
        raise ProfileError(
            f"品牌档案已存在：{target}。如需明确覆盖，请使用 --replace。"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def show_profile(args: argparse.Namespace) -> dict[str, Any]:
    target = profile_path(
        Path(args.output_root).expanduser().resolve(),
        args.brand_id,
    )
    if not target.is_file():
        raise ProfileError(f"品牌档案不存在：{target}")
    payload = read_json(target)
    validate_profile(payload)
    return payload


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_profile(args: argparse.Namespace) -> dict[str, Any]:
    stored = show_profile(args)
    products = stored["products"]
    if args.product_id:
        selected = next(
            (item for item in products if item.get("product_id") == args.product_id),
            None,
        )
        if selected is None:
            raise ProfileError(f"品牌档案中不存在产品：{args.product_id}")
    elif len(products) == 1:
        selected = products[0]
    else:
        raise ProfileError("品牌包含多个产品时必须提供 --product-id。")

    effective = {
        "schema_version": stored["schema_version"],
        "brand_id": stored["brand_id"],
        "brand_name": stored["brand_name"],
        "audiences": stored.get("audiences", []),
        "voice": stored.get("voice", {}),
        "visual": stored.get("visual", {}),
        "compliance": stored.get("compliance", {}),
        "defaults": stored.get("defaults", {}),
        "product": dict(selected),
    }
    if not args.overrides_file:
        return effective
    overrides = read_json(Path(args.overrides_file).expanduser().resolve())
    allowed = {"audiences", "voice", "visual", "compliance", "defaults", "product"}
    unexpected = sorted(set(overrides) - allowed)
    if unexpected:
        raise ProfileError(f"任务覆盖包含不允许的字段：{unexpected[0]}")
    product_overrides = overrides.get("product", {})
    if isinstance(product_overrides, dict) and "product_id" in product_overrides:
        raise ProfileError("任务覆盖不能修改 product_id。")
    return _deep_merge(effective, overrides)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=".brand_ugc")
    subparsers = parser.add_subparsers(dest="command", required=True)

    save = subparsers.add_parser("save", help="校验并保存品牌档案")
    save.add_argument("--profile-file", required=True)
    save.add_argument("--output-root", default=".brand_ugc")
    save.add_argument("--replace", action="store_true")

    show = subparsers.add_parser("show", help="读取一个品牌档案")
    show.add_argument("--brand-id", required=True)
    show.add_argument("--output-root", default=".brand_ugc")

    resolve = subparsers.add_parser("resolve", help="生成不写回档案的任务上下文")
    resolve.add_argument("--brand-id", required=True)
    resolve.add_argument("--product-id")
    resolve.add_argument("--overrides-file")
    resolve.add_argument("--output-root", default=".brand_ugc")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        operations = {
            "save": save_profile,
            "show": show_profile,
            "resolve": resolve_profile,
        }
        payload = operations[args.command](args)
    except ProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create, read, and resolve local brand profiles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


BRAND_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INSIGHT_SOURCES = ("interview", "local_asset", "platform_radar")
REF_FIELDS = ("run_id", "note_urls", "note")
LANGUAGE_BANK_FIELDS = (
    "voice_samples",
    "hook_patterns",
    "title_formulas",
    "avoid_patterns",
)
# 标题公式是受控枚举，与 xhs-topic-radar 策略卡的 titlePattern 保持一致。
TITLE_FORMULAS = (
    "number",
    "question",
    "pain-point",
    "result",
    "urgency",
    "authority",
)
MAX_OBSERVATIONS = 10
# 任务上下文里洞察的排序档位；置信度相同时再按 last_seen 比新鲜度。
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# 每个洞察分区的合并方式：key_fields 决定同一条目，list_fields 取并集，
# text_fields 由最新一次观察覆盖。
SECTION_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "audience_insights": {
        "key_fields": ("audience",),
        "list_fields": ("pain_points", "scenarios", "objections", "native_phrases"),
        "text_fields": (),
    },
    "content_pillars": {
        "key_fields": ("pillar",),
        "list_fields": ("angles", "audiences"),
        "text_fields": (),
    },
    "differentiation": {
        "key_fields": ("vs", "point"),
        "list_fields": (),
        "text_fields": ("evidence",),
    },
}


class ProfileError(ValueError):
    """Raised when a brand profile violates the public contract."""


def read_json(path: Path, label: str = "品牌档案") -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"无法读取{label}：{path}") from exc
    if not isinstance(payload, dict):
        raise ProfileError(f"{label}顶层必须是 JSON 对象。")
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


def insights_path(output_root: Path, brand_id: str) -> Path:
    if not BRAND_ID_RE.fullmatch(brand_id):
        raise ProfileError("brand_id 必须使用小写字母、数字和连字符。")
    return output_root / "brands" / brand_id / "insights.json"


def _string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProfileError(f"{label} 必须是数组。")
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ProfileError(f"{label}[{index}] 必须是非空字符串。")
        items.append(item.strip())
    return items


def _union(base: list[str], extra: list[str]) -> list[str]:
    merged = list(base)
    seen = set(merged)
    for item in extra:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _confidence(sources: list[str], observed_count: int) -> str:
    """出现次数和来源多样性共同决定置信度，不接受人工指定。"""
    if observed_count >= 3 and len(sources) >= 2:
        return "high"
    if observed_count >= 2 or len(sources) >= 2:
        return "medium"
    return "low"


def _merge_provenance(
    existing: dict[str, Any] | None,
    source: str,
    observed_at: str,
    ref: dict[str, Any] | None,
) -> dict[str, Any]:
    observation = {"source": source, "observed_at": observed_at}
    if ref is not None:
        observation["ref"] = ref
    if existing is None:
        sources = [source]
        observed_count = 1
        first_seen = observed_at
        last_seen = observed_at
        observations = [observation]
    else:
        observations = list(existing.get("observations", []))
        if observation in observations:
            # 同一次观察被重复合并（例如误跑两次同一份补丁），不重复计数。
            return dict(existing)
        sources = _union(existing.get("sources", []), [source])
        observed_count = int(existing.get("observed_count", 1)) + 1
        first_seen = min(existing.get("first_seen", observed_at), observed_at)
        last_seen = max(existing.get("last_seen", observed_at), observed_at)
        observations = [*observations, observation][-MAX_OBSERVATIONS:]
    return {
        "sources": sources,
        "observed_count": observed_count,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "confidence": _confidence(sources, observed_count),
        "observations": observations,
    }


def _entry_key(entry: dict[str, Any], key_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(entry[field] for field in key_fields)


def _validate_patch_entry(
    entry: Any,
    section: str,
    index: int,
    spec: dict[str, tuple[str, ...]],
    known_product_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ProfileError(f"{section}[{index}] 必须是对象。")
    allowed = {
        *spec["key_fields"],
        *spec["list_fields"],
        *spec["text_fields"],
        "product_ids",
    }
    unexpected = sorted(set(entry) - allowed)
    if unexpected:
        raise ProfileError(f"{section}[{index}] 包含不允许的字段：{unexpected[0]}")
    normalized: dict[str, Any] = {}
    for field in (*spec["key_fields"], *spec["text_fields"]):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ProfileError(f"{section}[{index}].{field} 不能为空。")
        normalized[field] = value.strip()
    for field in spec["list_fields"]:
        normalized[field] = _string_list(
            entry.get(field), f"{section}[{index}].{field}"
        )
    product_ids = _string_list(entry.get("product_ids"), f"{section}[{index}].product_ids")
    for product_id in product_ids:
        if product_id not in known_product_ids:
            raise ProfileError(
                f"{section}[{index}].product_ids 引用了品牌档案中不存在的产品："
                f"{product_id}"
            )
    normalized["product_ids"] = product_ids
    return normalized


def _validate_patch(patch: dict[str, Any], known_product_ids: set[str]) -> dict[str, Any]:
    allowed = {
        "brand_id",
        "source",
        "observed_at",
        "ref",
        "language_bank",
        *SECTION_SPECS,
    }
    unexpected = sorted(set(patch) - allowed)
    if unexpected:
        raise ProfileError(f"洞察补丁包含不允许的字段：{unexpected[0]}")

    source = patch.get("source")
    if source not in INSIGHT_SOURCES:
        raise ProfileError(f"source 必须是 {', '.join(INSIGHT_SOURCES)} 之一。")
    observed_at = patch.get("observed_at") or date.today().isoformat()
    if not isinstance(observed_at, str) or not DATE_RE.fullmatch(observed_at):
        raise ProfileError("observed_at 必须是 YYYY-MM-DD 格式。")

    ref = patch.get("ref")
    if ref is not None:
        if not isinstance(ref, dict):
            raise ProfileError("ref 必须是对象。")
        unexpected_ref = sorted(set(ref) - set(REF_FIELDS))
        if unexpected_ref:
            raise ProfileError(f"ref 包含不允许的字段：{unexpected_ref[0]}")
        if "note_urls" in ref:
            ref = {**ref, "note_urls": _string_list(ref["note_urls"], "ref.note_urls")}

    if source == "platform_radar" and patch.get("differentiation"):
        raise ProfileError(
            "platform_radar 回流的是品类信号，不能生成 differentiation；"
            "差异化主张需要品牌自行举证。"
        )

    sections: dict[str, list[dict[str, Any]]] = {}
    for section, spec in SECTION_SPECS.items():
        raw = patch.get(section)
        if raw is None:
            continue
        if not isinstance(raw, list):
            raise ProfileError(f"{section} 必须是数组。")
        sections[section] = [
            _validate_patch_entry(entry, section, index, spec, known_product_ids)
            for index, entry in enumerate(raw)
        ]

    language_bank: dict[str, list[str]] = {}
    raw_bank = patch.get("language_bank")
    if raw_bank is not None:
        if not isinstance(raw_bank, dict):
            raise ProfileError("language_bank 必须是对象。")
        unexpected_bank = sorted(set(raw_bank) - set(LANGUAGE_BANK_FIELDS))
        if unexpected_bank:
            raise ProfileError(
                f"language_bank 包含不允许的字段：{unexpected_bank[0]}"
            )
        for field in LANGUAGE_BANK_FIELDS:
            values = _string_list(raw_bank.get(field), f"language_bank.{field}")
            if field == "title_formulas":
                for value in values:
                    if value not in TITLE_FORMULAS:
                        raise ProfileError(
                            f"language_bank.title_formulas 只允许："
                            f"{'、'.join(TITLE_FORMULAS)}。"
                        )
            if values:
                language_bank[field] = values

    if not sections and not language_bank:
        raise ProfileError("洞察补丁没有任何可合并的内容。")

    return {
        "source": source,
        "observed_at": observed_at,
        "ref": ref,
        "sections": sections,
        "language_bank": language_bank,
    }


def load_insights(output_root: Path, brand_id: str) -> dict[str, Any] | None:
    target = insights_path(output_root, brand_id)
    if not target.is_file():
        return None
    payload = read_json(target, "品牌洞察")
    if payload.get("schema_version") != 1:
        raise ProfileError("insights.json 的 schema_version 当前只支持 1。")
    if payload.get("brand_id") != brand_id:
        raise ProfileError(f"insights.json 的 brand_id 与 {brand_id} 不一致。")
    return payload


def merge_insights(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root).expanduser().resolve()
    patch = read_json(Path(args.patch_file).expanduser().resolve(), "洞察补丁")
    brand_id = patch.get("brand_id")
    if brand_id != args.brand_id:
        raise ProfileError("洞察补丁的 brand_id 必须与 --brand-id 一致。")

    # 品牌档案是洞察的前提：product_ids 必须指向真实产品，避免孤立洞察。
    profile = read_json(profile_path(output_root, brand_id))
    validate_profile(profile)
    known_product_ids = {item["product_id"] for item in profile["products"]}

    parsed = _validate_patch(patch, known_product_ids)
    stored = load_insights(output_root, brand_id) or {
        "schema_version": 1,
        "brand_id": brand_id,
    }

    for section, entries in parsed["sections"].items():
        spec = SECTION_SPECS[section]
        existing = list(stored.get(section, []))
        index_by_key = {
            _entry_key(item, spec["key_fields"]): position
            for position, item in enumerate(existing)
        }
        for entry in entries:
            key = _entry_key(entry, spec["key_fields"])
            position = index_by_key.get(key)
            previous = existing[position] if position is not None else None
            merged = dict(previous) if previous else {}
            for field in spec["key_fields"]:
                merged[field] = entry[field]
            for field in spec["text_fields"]:
                merged[field] = entry[field]
            for field in spec["list_fields"]:
                values = _union(merged.get(field, []), entry[field])
                if values:
                    merged[field] = values
            product_ids = _union(merged.get("product_ids", []), entry["product_ids"])
            if product_ids:
                merged["product_ids"] = product_ids
            merged["provenance"] = _merge_provenance(
                previous.get("provenance") if previous else None,
                parsed["source"],
                parsed["observed_at"],
                parsed["ref"],
            )
            if position is None:
                index_by_key[key] = len(existing)
                existing.append(merged)
            else:
                existing[position] = merged
        stored[section] = existing

    if parsed["language_bank"]:
        bank = dict(stored.get("language_bank", {}))
        for field, values in parsed["language_bank"].items():
            bank[field] = _union(bank.get(field, []), values)
        stored["language_bank"] = bank

    target = insights_path(output_root, brand_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return stored


def show_insights(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output_root).expanduser().resolve()
    stored = load_insights(output_root, args.brand_id)
    if stored is None:
        raise ProfileError(f"品牌洞察不存在：{insights_path(output_root, args.brand_id)}")
    return stored


def _insight_priority(entry: dict[str, Any]) -> tuple[int, int]:
    """先看有多可靠，同样可靠的看谁更新；缺 provenance 的排最后。"""
    provenance = entry.get("provenance") or {}
    rank = CONFIDENCE_ORDER.get(provenance.get("confidence"), len(CONFIDENCE_ORDER))
    digits = str(provenance.get("last_seen") or "").replace("-", "")
    recency = -int(digits) if digits.isdigit() else 0
    return (rank, recency)


def _select_insights(stored: dict[str, Any], product_id: str) -> dict[str, Any]:
    """保留品牌级条目（product_ids 为空）和命中当前产品的条目，并按优先级排序。"""
    selected: dict[str, Any] = {}
    for section in SECTION_SPECS:
        entries = [
            entry
            for entry in stored.get(section, [])
            if not entry.get("product_ids") or product_id in entry["product_ids"]
        ]
        if entries:
            selected[section] = sorted(entries, key=_insight_priority)
    language_bank = stored.get("language_bank")
    if language_bank:
        selected["language_bank"] = language_bank
    return selected


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
    stored_insights = load_insights(
        Path(args.output_root).expanduser().resolve(),
        stored["brand_id"],
    )
    if stored_insights is not None:
        insights = _select_insights(stored_insights, selected["product_id"])
        if insights:
            effective["insights"] = insights
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

    insights_merge = subparsers.add_parser(
        "insights-merge", help="把一次采集的洞察补丁并入品牌洞察"
    )
    insights_merge.add_argument("--brand-id", required=True)
    insights_merge.add_argument("--patch-file", required=True)
    insights_merge.add_argument("--output-root", default=".brand_ugc")

    insights_show = subparsers.add_parser("insights-show", help="读取一个品牌的洞察")
    insights_show.add_argument("--brand-id", required=True)
    insights_show.add_argument("--output-root", default=".brand_ugc")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        operations = {
            "save": save_profile,
            "show": show_profile,
            "resolve": resolve_profile,
            "insights-merge": merge_insights,
            "insights-show": show_insights,
        }
        payload = operations[args.command](args)
    except ProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""brand-profile 和 ugc-image-post 各自实现了洞察排序，两者必须给出相同顺序。

Skills 可以被独立安装，不能跨目录 import，所以排序逻辑是有意重复的。这里用同一组
条目校验两份实现的行为一致，避免只改了其中一处。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATIONS = {
    "brand-profile": ROOT / "brand-profile" / "scripts" / "manage_profile.py",
    "ugc-image-post": ROOT / "ugc-image-post" / "scripts" / "run_pipeline.py",
}


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(audience: str, confidence: str | None, last_seen: str | None) -> dict:
    provenance: dict[str, Any] = {}
    if confidence is not None:
        provenance["confidence"] = confidence
    if last_seen is not None:
        provenance["last_seen"] = last_seen
    entry: dict[str, Any] = {"audience": audience}
    if provenance:
        entry["provenance"] = provenance
    return entry


class InsightPriorityParityTests(unittest.TestCase):
    def test_both_skills_rank_the_same_entries_identically(self) -> None:
        entries = [
            _entry("低置信最新", "low", "2026-03-01"),
            _entry("高置信较旧", "high", "2026-01-03"),
            _entry("高置信较新", "high", "2026-02-03"),
            _entry("中置信", "medium", "2026-02-10"),
            _entry("缺少置信度", None, "2026-04-01"),
            _entry("完全没有来源记录", None, None),
        ]
        expected = [
            "高置信较新",
            "高置信较旧",
            "中置信",
            "低置信最新",
            "缺少置信度",
            "完全没有来源记录",
        ]

        for name, path in IMPLEMENTATIONS.items():
            module = _load(name, path)
            ordered = sorted(entries, key=module._insight_priority)
            self.assertEqual(
                [item["audience"] for item in ordered],
                expected,
                f"{name} 的洞察排序与约定不一致",
            )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Check local dependencies, installed Skills, and credential status for brand-ugc."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
LOCAL_SUITE_ROOT = SKILL_DIR.parent
GLOBAL_SKILLS_ROOT = Path.home() / ".agents" / "skills"

SKILL_NAMES = [
    "ask-brand",
    "xhs-topic-radar",
    "brand-profile",
    "ugc-image-post",
    "ugc-storyboard",
    "image-generator",
]

CJK_FONT_PATTERN = re.compile(
    r"Noto Sans CJK SC|PingFang|Microsoft YaHei|Heiti|WenQuanYi", re.IGNORECASE
)


def _tool_status(binary: str, *version_args: str) -> dict:
    exe = shutil.which(binary)
    if not exe:
        return {"found": False, "path": None, "version": None}
    try:
        result = subprocess.run(
            [exe, *version_args], capture_output=True, text=True, timeout=10, check=False
        )
    except OSError:
        return {"found": True, "path": exe, "version": None}
    combined = (result.stdout or "") + (result.stderr or "")
    line = next((entry.strip() for entry in combined.splitlines() if entry.strip()), "")
    return {"found": True, "path": exe, "version": line}


def _python_status() -> dict:
    info = sys.version_info
    return {
        "found": True,
        "path": sys.executable,
        "version": f"{info.major}.{info.minor}.{info.micro}",
        "ok": (info.major, info.minor) >= (3, 10),
    }


def _node_status() -> dict:
    status = _tool_status("node", "--version")
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", status["version"] or "")
    ok_for_topic_radar = False
    if match:
        major, minor, _patch = (int(part) for part in match.groups())
        ok_for_topic_radar = (major, minor) >= (22, 5)
    status["ok_for_topic_radar"] = ok_for_topic_radar
    return status


def _cjk_font_status() -> dict:
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return {
            "checked": False,
            "found": None,
            "note": "未找到 fc-list，无法自动检测中文字体，请手动确认。",
        }
    try:
        result = subprocess.run([fc_list], capture_output=True, text=True, timeout=10, check=False)
    except OSError:
        return {"checked": False, "found": None, "note": "fc-list 执行失败，请手动确认中文字体。"}
    found = bool(CJK_FONT_PATTERN.search(result.stdout))
    return {"checked": True, "found": found, "note": ""}


def _installed_skills() -> dict:
    installed = {}
    for name in SKILL_NAMES:
        global_path = GLOBAL_SKILLS_ROOT / name
        local_path = LOCAL_SUITE_ROOT / name
        if global_path.is_dir():
            installed[name] = {"installed": True, "mode": "global", "path": str(global_path)}
        elif local_path.is_dir() and local_path != SKILL_DIR:
            installed[name] = {"installed": True, "mode": "local", "path": str(local_path)}
        else:
            installed[name] = {"installed": False, "mode": None, "path": None}
    return installed


def _evolink_key_status() -> dict:
    for name in ("EVOLINK_API_KEY", "IMAGEGEN_API_KEY"):
        if os.environ.get(name, "").strip():
            return {"configured": True, "source": "environment", "path": None}
    for base in (GLOBAL_SKILLS_ROOT, LOCAL_SUITE_ROOT):
        secret_file = base / "image-generator" / "secrets" / "api_key.txt"
        if secret_file.is_file() and secret_file.read_text(encoding="utf-8-sig").strip():
            return {"configured": True, "source": "local-file", "path": str(secret_file)}
    return {"configured": False, "source": None, "path": None}


def _tikhub_key_status() -> dict:
    if os.environ.get("TIKHUB_API_KEY", "").strip():
        return {"configured": True, "source": "environment", "path": None}
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    credential_file = config_home / "pi-xhs-topic-radar" / "credentials.json"
    if credential_file.is_file():
        try:
            data = json.loads(credential_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if str(data.get("tikhubApiKey", "")).strip():
            return {"configured": True, "source": "local-file", "path": str(credential_file)}
    return {"configured": False, "source": None, "path": None}


def _brand_profiles(project_root: str) -> list[str]:
    brands_dir = Path(project_root).expanduser().resolve() / ".brand_ugc" / "brands"
    if not brands_dir.is_dir():
        return []
    return sorted(
        entry.name for entry in brands_dir.iterdir() if (entry / "profile.json").is_file()
    )


def cmd_check(args: argparse.Namespace) -> int:
    report = {
        "schema_version": 1,
        "python": _python_status(),
        "node": _node_status(),
        "imagemagick": _tool_status("magick", "-version"),
        "cjk_font": _cjk_font_status(),
        "ffmpeg": _tool_status("ffmpeg", "-version"),
        "ffprobe": _tool_status("ffprobe", "-version"),
        "skills": _installed_skills(),
        "credentials": {
            "evolink": _evolink_key_status(),
            "tikhub": _tikhub_key_status(),
        },
        "brand_profiles": _brand_profiles(args.project_root),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_set_evolink_key(_args: argparse.Namespace) -> int:
    key = sys.stdin.read().strip()
    if not key:
        raise SystemExit("未从标准输入读取到 Key，已取消。")
    if re.search(r"\s", key):
        raise SystemExit("EvoLink API Key 不能包含空格或换行。")

    target_root = (
        GLOBAL_SKILLS_ROOT
        if (GLOBAL_SKILLS_ROOT / "image-generator").is_dir()
        else LOCAL_SUITE_ROOT
    )
    secret_dir = target_root / "image-generator" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(secret_dir, 0o700)

    secret_file = secret_dir / "api_key.txt"
    temporary_file = secret_dir / f".api_key.txt.{os.getpid()}.tmp"
    temporary_file.write_text(key + "\n", encoding="utf-8")
    os.chmod(temporary_file, 0o600)
    temporary_file.replace(secret_file)
    os.chmod(secret_file, 0o600)

    print(json.dumps({"configured": True, "path": str(secret_file)}, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check", help="Report dependency, install, and credential status as JSON."
    )
    check_parser.add_argument("--project-root", default=".")
    check_parser.set_defaults(func=cmd_check)

    set_key_parser = subparsers.add_parser(
        "set-evolink-key",
        help="Read an EvoLink API Key from stdin and save it to the local secrets file.",
    )
    set_key_parser.set_defaults(func=cmd_set_evolink_key)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

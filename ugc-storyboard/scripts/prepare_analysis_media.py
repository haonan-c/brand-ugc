#!/usr/bin/env python3
"""Create a local max-720p video proxy and mono analysis audio track."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def probe(path: str | Path) -> dict[str, Any]:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ffprobe 失败：{path}")
    return json.loads(proc.stdout)


def prepare(video: Path, proxy: Path, audio: Path) -> dict[str, Any]:
    proxy.parent.mkdir(parents=True, exist_ok=True)
    audio.parent.mkdir(parents=True, exist_ok=True)
    proxy_proc = run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-vf",
            r"scale=-2:min(720\,ih)",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(proxy),
        ]
    )
    if proxy_proc.returncode != 0 or not proxy.exists():
        raise RuntimeError(proxy_proc.stderr.strip() or "分析代理视频生成失败")

    audio_proc = run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-map",
            "0:a:0?",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(audio),
        ]
    )
    if audio_proc.returncode != 0 or not audio.exists() or audio.stat().st_size == 0:
        audio.unlink(missing_ok=True)

    proxy_info = probe(proxy)
    video_stream = next(
        stream for stream in proxy_info["streams"] if stream.get("codec_type") == "video"
    )
    manifest: dict[str, Any] = {
        "source_file": video.name,
        "proxy": {
            "file": str(proxy.resolve()),
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "has_audio": any(
                stream.get("codec_type") == "audio"
                for stream in proxy_info["streams"]
            ),
        },
        "audio": None,
    }
    if audio.exists():
        audio_info = probe(audio)
        audio_stream = next(
            stream for stream in audio_info["streams"] if stream.get("codec_type") == "audio"
        )
        manifest["audio"] = {
            "file": str(audio.resolve()),
            "channels": int(audio_stream["channels"]),
            "sample_rate": int(audio_stream["sample_rate"]),
        }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.is_file():
        raise SystemExit(f"原视频不存在：{video}")
    manifest = prepare(
        video,
        Path(args.proxy).expanduser().resolve(),
        Path(args.audio).expanduser().resolve(),
    )
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

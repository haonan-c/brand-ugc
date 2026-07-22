#!/usr/bin/env python3
"""Extract 12 local frames from the original video and build one 3x4 collage."""

from __future__ import annotations

import argparse
import json
import re
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


def ffprobe_duration(video: str | Path) -> float:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ffprobe 失败：{video}")
    return float(proc.stdout.strip())


def parse_timepoint(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"不支持的时间戳：{value}")


def read_timepoints(path: str | Path) -> list[float]:
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    points = [parse_timepoint(item) for item in re.split(r"[,，\n]+", text) if item.strip()]
    if len(points) != 12:
        raise ValueError(f"需要恰好 12 个时间点，实际为 {len(points)}")
    return points


def read_storyboard_timepoints(path: str | Path) -> list[float]:
    text = Path(path).read_text(encoding="utf-8-sig")
    fields = re.findall(r"时间\s*[:：]\s*[\"“”']([^\"“”']+)[\"“”']", text)
    starts = [parse_timepoint(item.split("-", 1)[0]) for item in fields]
    if len(starts) != 12:
        raise ValueError(f"需要恰好 12 个分镜时间字段，实际为 {len(starts)}")
    return starts


def read_storyboard_json_timepoints(path: str | Path) -> list[float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    shots = payload.get("shots", [])
    if len(shots) != 12:
        raise ValueError(f"需要恰好 12 个 JSON 分镜，实际为 {len(shots)}")
    return [
        (float(shot["start_seconds"]) + float(shot["end_seconds"])) / 2
        for shot in shots
    ]


def extract_frames(
    video: str | Path,
    timepoints: list[float],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    duration = ffprobe_duration(video)
    frames: list[dict[str, Any]] = []
    for index, point in enumerate(timepoints, 1):
        seconds = min(max(point, 0.0), max(duration - 0.02, 0.0))
        frame = output / f"frame_{index:02d}.jpg"
        proc = run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{seconds:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame),
            ]
        )
        if proc.returncode != 0 or not frame.exists():
            raise RuntimeError(proc.stderr.strip() or f"第 {index} 帧抽取失败")
        frames.append(
            {
                "index": index,
                "seconds": round(seconds, 3),
                "path": str(frame.resolve()),
            }
        )
    return frames


def make_collage(frames_dir: str | Path, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "1",
            "-start_number",
            "1",
            "-i",
            str(Path(frames_dir) / "frame_%02d.jpg"),
            "-vf",
            (
                "scale=480:640:force_original_aspect_ratio=increase,"
                "crop=480:640,tile=3x4:padding=0:margin=0"
            ),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output),
        ]
    )
    if proc.returncode != 0 or not output.exists():
        raise RuntimeError(proc.stderr.strip() or "十二宫格拼接失败")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--timepoints")
    source.add_argument("--storyboard")
    source.add_argument("--storyboard-json")
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--collage", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    if args.timepoints:
        points = read_timepoints(args.timepoints)
    elif args.storyboard_json:
        points = read_storyboard_json_timepoints(args.storyboard_json)
    else:
        points = read_storyboard_timepoints(args.storyboard)

    frames = extract_frames(args.video, points, args.frames_dir)
    collage = make_collage(args.frames_dir, args.collage)
    payload = {
        "video_file": Path(args.video).name,
        "timepoints_seconds": [round(item, 3) for item in points],
        "frames": frames,
        "frame_count": len(frames),
        "collage": str(collage.resolve()),
        "collage_layout": {"columns": 3, "rows": 4, "panels": 12},
    }
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE_MEDIA = (
    ROOT
    / "ugc-storyboard"
    / "scripts"
    / "prepare_analysis_media.py"
)
EXTRACT_FRAMES = (
    ROOT
    / "ugc-storyboard"
    / "scripts"
    / "extract_12_frames.py"
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 FFmpeg")
class AnalysisMediaContractTests(unittest.TestCase):
    def test_cli_creates_720p_silent_proxy_and_mono_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "原始 视频.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=1280x960:rate=12:duration=1",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    str(original),
                ],
                check=True,
                capture_output=True,
            )
            proxy = root / "analysis_proxy.mp4"
            audio = root / "analysis_audio.m4a"
            manifest = root / "manifest.json"

            subprocess.run(
                [
                    sys.executable,
                    str(PREPARE_MEDIA),
                    "--video",
                    str(original),
                    "--proxy",
                    str(proxy),
                    "--audio",
                    str(audio),
                    "--manifest",
                    str(manifest),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            info = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(info["proxy"]["height"], 720)
            self.assertFalse(info["proxy"]["has_audio"])
            self.assertEqual(info["audio"]["channels"], 1)
            self.assertEqual(info["audio"]["sample_rate"], 16000)
            self.assertNotEqual(proxy.read_bytes(), original.read_bytes())

    def test_json_storyboard_drives_twelve_frame_ffmpeg_collage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "原片 空格.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=360x640:rate=24:duration=1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                ],
                check=True,
                capture_output=True,
            )
            shots = []
            for index in range(1, 13):
                shots.append(
                    {
                        "index": index,
                        "start_seconds": (index - 1) / 12,
                        "end_seconds": index / 12,
                    }
                )
            storyboard = root / "analysis.json"
            storyboard.write_text(
                json.dumps({"shots": shots}),
                encoding="utf-8",
            )
            collage = root / "12宫格参考图.jpg"
            manifest = root / "frames.json"

            subprocess.run(
                [
                    sys.executable,
                    str(EXTRACT_FRAMES),
                    "--video",
                    str(video),
                    "--storyboard-json",
                    str(storyboard),
                    "--frames-dir",
                    str(root / "帧"),
                    "--collage",
                    str(collage),
                    "--manifest",
                    str(manifest),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            info = json.loads(manifest.read_text(encoding="utf-8"))
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    str(collage),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            dimensions = json.loads(probe.stdout)["streams"][0]

        self.assertEqual(info["frame_count"], 12)
        self.assertEqual(info["collage_layout"], {"columns": 3, "rows": 4, "panels": 12})
        self.assertEqual(dimensions, {"width": 1440, "height": 2560})


if __name__ == "__main__":
    unittest.main()

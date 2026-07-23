from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "brand-ugc"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from run_public_pipeline import run_pipeline  # noqa: E402


def _timeline() -> list[tuple[float, float]]:
    return [((index - 1) * 1.25, index * 1.25) for index in range(1, 13)]


def _analysis_payload() -> dict:
    shots = []
    for index, (start, end) in enumerate(_timeline(), 1):
        shots.append(
            {
                "index": index,
                "source": "observed",
                "start_seconds": start,
                "end_seconds": end,
                "visual_description": f"镜头{index}展示产品",
                "shot_size": "close_up",
                "camera_movement": "static",
                "composition": "主体居中",
                "action": "稳定展示",
                "product_presence": True,
                "person_presence": False,
                "on_screen_text": "",
                "audio_cue": "",
                "adaptation_function": "产品认知",
            }
        )
    return {
        "duration_seconds": 15,
        "summary": "测试电商视频",
        "audio": {
            "has_audio": False,
            "voiceover_summary": "",
            "music_mood": "",
            "transcript": [],
        },
        "shots": shots,
    }


def _new_script_payload() -> dict:
    shots = []
    for index, (start, end) in enumerate(_timeline(), 1):
        shots.append(
            {
                "index": index,
                "source_mapping_index": index,
                "start_seconds": start,
                "end_seconds": end,
                "beat": "展示",
                "scene": "真实桌面",
                "visual_description": f"镜头{index}展示新产品",
                "shot_size": "close_up",
                "camera_movement": "static",
                "composition": "主体居中",
                "action": "产品稳定展示",
                "product_direction": "保持参考图外观",
                "person_direction": "不出现人物",
                "copy": "",
                "audio_cue": "",
                "mapping_rationale": "保持原镜头传播功能",
            }
        )
    return {
        "product_summary": "测试产品",
        "facts_used": ["产品为蓝色"],
        "needs_confirmation": [],
        "person_policy": "no_person",
        "adaptation_summary": "保留原节奏并替换产品",
        "shots": shots,
    }


def _shot_prompts_payload() -> dict:
    shots = []
    for index, (start, end) in enumerate(_timeline(), 1):
        shots.append(
            {
                "index": index,
                "start_seconds": start,
                "end_seconds": end,
                "image_prompt": f"镜头{index}，蓝色产品位于真实桌面中央",
                "negative_prompt": "字幕，水印，平台UI，产品变形",
                "motion_intent": "固定镜头，产品轻微高光移动",
                "product_presence": True,
                "person_presence": False,
                "on_screen_text": "",
                "mapping_rationale": "对应原镜头构图",
            }
        )
    return {
        "series_lock": {
            "product": "蓝色产品，外观一致",
            "person": "不出现人物",
            "environment": "真实桌面",
            "lighting": "柔和侧光",
            "color_grade": "自然商业色调",
        },
        "shots": shots,
    }


def _qa_payload() -> dict:
    return {
        "pass": True,
        "grid": {"columns": 3, "rows": 4, "panels": 12, "order_correct": True},
        "checks": {
            "clean_frame": True,
            "composition_match": True,
            "product_consistency": True,
            "person_consistency": True,
            "realistic_background": True,
            "shot_mapping": True,
        },
        "issues": [],
        "correction_prompt": "",
    }


def _video_prompt_payload() -> dict:
    return {
        "master_prompt": "以十二宫格为镜头与节奏参考，生成15秒写实电商产品视频。",
        "shots": [
            {
                "index": index,
                "start_seconds": start,
                "end_seconds": end,
                "motion_instruction": "固定镜头，产品高光自然移动。",
            }
            for index, (start, end) in enumerate(_timeline(), 1)
        ],
    }


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "需要 FFmpeg")
class OfflinePipelineTests(unittest.TestCase):
    def test_full_pipeline_and_resume_without_secret_or_duplicate_submission(self) -> None:
        counts = {"credits": 0, "content": 0, "uploads": 0, "images": 0, "tasks": 0}
        request_bodies: list[str] = []
        image_bytes = b""
        task_counter = 0

        payloads = {
            "品牌 UGC 视频解析": _analysis_payload,
            "新产品12分镜脚本": _new_script_payload,
            "十二宫格分镜提示词": _shot_prompts_payload,
            "十二宫格图片视觉QA": _qa_payload,
            "Seedance十五秒视频提示词": _video_prompt_payload,
        }

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                return None

            def _json(self, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                nonlocal image_bytes
                if self.path == "/v1/credits":
                    counts["credits"] += 1
                    self._json(
                        {
                            "success": True,
                            "data": {
                                "token": {
                                    "remaining_credits": 100,
                                    "unlimited_credits": False,
                                }
                            },
                        }
                    )
                    return
                if self.path.startswith("/v1/tasks/"):
                    counts["tasks"] += 1
                    task_id = self.path.rsplit("/", 1)[-1]
                    self._json(
                        {
                            "id": task_id,
                            "status": "completed",
                            "model": "gemini-3-pro-image-preview",
                            "progress": 100,
                            "results": [f"http://127.0.0.1:{self.server.server_port}/generated.png"],
                        }
                    )
                    return
                if self.path == "/generated.png":
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(image_bytes)))
                    self.end_headers()
                    self.wfile.write(image_bytes)
                    return
                self.send_error(404)

            def do_POST(self) -> None:
                nonlocal task_counter
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                text = raw.decode("utf-8", errors="replace")
                request_bodies.append(text)
                if self.path == "/api/v1/files/upload/base64":
                    counts["uploads"] += 1
                    self._json(
                        {
                            "success": True,
                            "data": {
                                "file_id": f"file-{counts['uploads']}",
                                "file_url": f"http://127.0.0.1:{self.server.server_port}/uploaded.png",
                                "expires_at": "2099-01-01T00:00:00Z",
                            },
                        }
                    )
                    return
                if self.path == "/v1/images/generations":
                    counts["images"] += 1
                    task_counter += 1
                    self._json(
                        {
                            "id": f"task-unified-{task_counter}",
                            "status": "pending",
                            "model": "gemini-3-pro-image-preview",
                            "progress": 0,
                        }
                    )
                    return
                if self.path.endswith(":generateContent"):
                    counts["content"] += 1
                    request = json.loads(text)
                    title = request["generationConfig"]["responseJsonSchema"]["title"]
                    content = json.dumps(payloads[title](), ensure_ascii=False)
                    self._json(
                        {
                            "responseId": f"response-{counts['content']}",
                            "modelVersion": "gemini-3.1-pro-preview",
                            "candidates": [
                                {"content": {"parts": [{"text": content}]}}
                            ],
                            "usageMetadata": {"totalTokenCount": 100},
                        }
                    )
                    return
                self.send_error(404)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                video = root / "对标 视频.mp4"
                product = root / "产品 图.png"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=180x320:rate=6:duration=15",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        str(video),
                    ],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=blue:size=64x64",
                        "-frames:v",
                        "1",
                        str(product),
                    ],
                    check=True,
                    capture_output=True,
                )
                image_bytes = product.read_bytes()
                base = f"http://127.0.0.1:{server.server_port}"
                config = root / "config.json"
                config.write_text(
                    json.dumps(
                        {
                            "api": {
                                "text_base_url": base,
                                "api_base_url": base,
                                "files_base_url": base,
                                "api_key_file": "missing.txt",
                                "request_timeout_seconds": 10,
                                "request_retries": 1,
                                "poll_interval_seconds": 0,
                                "poll_timeout_seconds": 5,
                            },
                            "models": {
                                "analysis": "gemini-3.1-pro-preview",
                                "image": "gemini-3-pro-image-preview",
                            },
                            "limits": {"max_model_requests": 14},
                        }
                    ),
                    encoding="utf-8",
                )
                output_root = root / "运行 输出"
                args = argparse.Namespace(
                    run_name="案例一",
                    video=str(video),
                    product_image=str(product),
                    person_image=None,
                    copy_file=None,
                    product_info="测试产品，蓝色。",
                    product_info_file=None,
                    config=str(config),
                    output_root=str(output_root),
                    resolution="1K",
                    resume=False,
                )

                with patch.dict(os.environ, {"EVOLINK_API_KEY": "fake-secret"}, clear=False):
                    with redirect_stdout(io.StringIO()):
                        first = run_pipeline(args)
                    model_counts = (counts["content"], counts["images"])
                    args.resume = True
                    with redirect_stdout(io.StringIO()):
                        second = run_pipeline(args)

                run_dir = output_root / "案例一"
                reported_deliverables = {
                    name: Path(path).name
                    for name, path in first["deliverables"].items()
                }
                deliverable_names = sorted(
                    path.name
                    for path in (run_dir / "deliverables").iterdir()
                    if path.is_file()
                )
                prompt_text = (run_dir / "outputs" / "视频提示词1-12.txt").read_text(
                    encoding="utf-8"
                )
                persisted_text = "\n".join(
                    path.read_text(encoding="utf-8", errors="ignore")
                    for path in run_dir.rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in {".json", ".jsonl", ".txt", ".md", ".log"}
                )

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(model_counts, (6, 2))
        self.assertEqual((counts["content"], counts["images"]), model_counts)
        self.assertEqual(first["request_budget"]["used"], 8)
        self.assertEqual(second["request_budget"]["used"], 8)
        self.assertEqual(
            reported_deliverables,
            {
                "final_storyboard": "最终12宫格分镜图.png",
                "video_prompt": "视频提示词1-12.txt",
                "qa_report": "QA报告.json",
            },
        )
        self.assertEqual(
            first["conversation_output"]["final_image"],
            first["deliverables"]["final_storyboard"],
        )
        self.assertEqual(
            deliverable_names,
            ["QA报告.json", "最终12宫格分镜图.png", "视频提示词1-12.txt"],
        )
        self.assertIn("12条分镜运动指令", prompt_text)
        self.assertNotIn("fake-secret", persisted_text)
        self.assertNotIn("base64,", persisted_text)
        self.assertNotIn("http://127.0.0.1", persisted_text)
        for marker in (
            "短视频" + "12分镜解析" + "Skill",
            "短视频" + "12分镜新产品脚本" + "Skill",
            "短视频" + "12分镜提示词" + "Skill",
            "12分镜" + "模板图" + "Skill",
            "12分镜" + "最终生成图" + "Skill",
            "12分镜" + "视频生成提示词" + "Skill",
        ):
            self.assertFalse(any(marker in body for body in request_bodies))


if __name__ == "__main__":
    unittest.main()

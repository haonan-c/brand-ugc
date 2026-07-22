from __future__ import annotations

import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "brand-ugc"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))

from evolink_client import (  # noqa: E402
    EvoLinkError,
    EvoLinkClient,
    build_generate_content_payload,
    load_api_key,
)


class ApiKeyContractTests(unittest.TestCase):
    def test_api_key_migration_precedence_and_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            key_file = Path(tmp) / "api_key.txt"
            key_file.write_text("file-key\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"EVOLINK_API_KEY": "evolink-key", "IMAGEGEN_API_KEY": "legacy-key"},
                clear=True,
            ):
                self.assertEqual(load_api_key(key_file), "evolink-key")

            with patch.dict(os.environ, {"IMAGEGEN_API_KEY": "legacy-key"}, clear=True):
                self.assertEqual(load_api_key(key_file), "legacy-key")

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(load_api_key(key_file), "file-key")

            key_file.unlink()
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(EvoLinkError, "EVOLINK_API_KEY"):
                    load_api_key(key_file)


class NativePayloadContractTests(unittest.TestCase):
    def test_builds_gemini_native_multimodal_json_schema_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "产品 图.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            schema = {
                "type": "object",
                "required": ["shots"],
                "properties": {
                    "shots": {
                        "type": "array",
                        "minItems": 12,
                        "maxItems": 12,
                    }
                },
            }

            payload = build_generate_content_payload(
                "请严格输出十二分镜。",
                [image],
                schema=schema,
                max_output_tokens=16000,
            )

        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][0]["parts"][0], {"text": "请严格输出十二分镜。"})
        self.assertEqual(
            payload["contents"][0]["parts"][1]["inlineData"]["mimeType"],
            "image/png",
        )
        self.assertNotIn("fileUri", payload["contents"][0]["parts"][1])
        self.assertEqual(
            payload["generationConfig"]["responseJsonSchema"],
            schema,
        )
        self.assertEqual(
            payload["generationConfig"]["responseMimeType"],
            "application/json",
        )
        self.assertNotIn("{{", str(payload))

    def test_json_requests_include_browser_compatible_user_agent(self) -> None:
        captured = []

        def opener(request, timeout=0):
            captured.append(request)
            return _FakeResponse(b'{"success": true}')

        client = EvoLinkClient(api_key="test-key", opener=opener)
        client.get_credits()

        self.assertEqual(len(captured), 1)
        self.assertIn("Mozilla/5.0", captured[0].get_header("User-agent"))


class _FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self.body = body
        self.headers = {"content-type": content_type}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class AsyncImageResumeContractTests(unittest.TestCase):
    def test_existing_task_is_polled_without_resubmission_or_persisted_url(self) -> None:
        requests = []

        def opener(request, timeout=0):
            requests.append(request)
            if "/v1/tasks/" in request.full_url:
                return _FakeResponse(
                    json.dumps(
                        {
                            "id": "task-unified-existing",
                            "status": "completed",
                            "model": "gemini-3-pro-image-preview",
                            "progress": 100,
                            "results": ["https://temporary.example/generated.png"],
                        }
                    ).encode()
                )
            if request.full_url == "https://temporary.example/generated.png":
                return _FakeResponse(b"\x89PNG\r\n\x1a\nimage", "image/png")
            raise AssertionError(f"unexpected request: {request.full_url}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "task.json"
            state.write_text(
                json.dumps(
                    {
                        "task_id": "task-unified-existing",
                        "status": "processing",
                        "model": "gemini-3-pro-image-preview",
                    }
                ),
                encoding="utf-8",
            )
            output = root / "image-01.png"
            client = EvoLinkClient(
                api_key="test-key",
                opener=opener,
                sleep=lambda _: None,
            )

            result = client.generate_image(
                prompt="生成严格的4×3十二宫格",
                reference_images=[],
                output_path=output,
                state_path=state,
                quality="2K",
                aspect_ratio="9:16",
                poll_interval=0,
            )

            persisted = state.read_text(encoding="utf-8")
            output_header = output.read_bytes()[:8]

        self.assertEqual(result, output.resolve())
        self.assertEqual(output_header, b"\x89PNG\r\n\x1a\n")
        self.assertFalse(any("/v1/images/generations" in req.full_url for req in requests))
        self.assertFalse(any("/files/upload/" in req.full_url for req in requests))
        self.assertNotIn("https://", persisted)


if __name__ == "__main__":
    unittest.main()

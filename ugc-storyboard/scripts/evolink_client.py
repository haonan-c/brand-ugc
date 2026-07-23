#!/usr/bin/env python3
"""EvoLink API adapter shared by the public ecommerce workflow."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class EvoLinkError(RuntimeError):
    """Raised when EvoLink configuration or requests fail."""


def load_api_key(key_file: str | Path) -> str:
    """Load one EvoLink key while preserving the legacy environment fallback."""

    for name in ("EVOLINK_API_KEY", "IMAGEGEN_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value

    path = Path(key_file).expanduser()
    if path.exists():
        value = path.read_text(encoding="utf-8-sig").strip()
        if value:
            return value

    raise EvoLinkError(
        f"缺少 EvoLink API Key。请设置 EVOLINK_API_KEY，"
        f"或将密钥写入 {path}。"
    )


def file_inline_part(path: str | Path) -> dict[str, Any]:
    """Encode one local proxy/audio/image as a Gemini Native inline part."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise EvoLinkError(f"媒体文件不存在：{source}")
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    return {
        "inlineData": {
            "mimeType": mime_type,
            "data": base64.b64encode(source.read_bytes()).decode("ascii"),
        }
    }


def build_generate_content_payload(
    prompt: str,
    media_files: list[str | Path] | None = None,
    *,
    schema: dict[str, Any] | None = None,
    max_output_tokens: int = 16000,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Build the documented Gemini Native generateContent request."""

    if "{{" in prompt or "}}" in prompt:
        raise EvoLinkError("运行提示词仍包含已废弃的 {{...Skill}} 模块标记。")
    parts: list[dict[str, Any]] = [{"text": prompt}]
    parts.extend(file_inline_part(path) for path in (media_files or []))
    generation_config: dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
    }
    if schema is not None:
        generation_config.update(
            {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            }
        )
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }


def extract_generated_text(response: dict[str, Any]) -> str:
    """Extract visible model text while excluding Gemini thinking parts."""

    candidates = response.get("candidates") or []
    if not candidates:
        raise EvoLinkError("EvoLink 响应中没有 candidates。")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    visible = [
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict) and part.get("text") and not part.get("thought")
    ]
    if not visible:
        raise EvoLinkError("EvoLink 响应中没有可见文本。")
    return "\n".join(visible).strip()


def estimate_prompt_tokens(text: str) -> int:
    """Conservatively estimate tokens for the 2000-token image prompt limit."""

    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    other = max(len(text) - cjk, 0)
    return cjk + (other + 3) // 4


def limit_image_prompt(text: str, maximum_tokens: int = 1900) -> str:
    stripped = text.strip()
    if estimate_prompt_tokens(stripped) <= maximum_tokens:
        return stripped
    output: list[str] = []
    used = 0
    for character in stripped:
        cost = 1 if re.match(r"[\u3400-\u9fff]", character) else 0.25
        if used + cost > maximum_tokens:
            break
        output.append(character)
        used += cost
    return "".join(output).rstrip() + "\n（已按接口上限截断，严格保持上述约束。）"


def _safe_error_body(text: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization|api[_-]?key|token)[\"'\s:=]+[^,\s\"']+",
        r"\1=[已脱敏]",
        text,
    )
    redacted = re.sub(r"data:[^;]+;base64,[A-Za-z0-9+/=]+", "[Base64已脱敏]", redacted)
    return redacted[:1000]


class EvoLinkClient:
    """Thin adapter for Gemini Native, file upload, and async image tasks."""

    def __init__(
        self,
        *,
        api_key: str,
        text_base_url: str = "https://direct.evolink.ai",
        api_base_url: str = "https://api.evolink.ai",
        files_base_url: str = "https://files-api.evolink.ai",
        text_model: str = "gemini-3.1-pro-preview",
        image_model: str = "gemini-3-pro-image-preview",
        timeout: int = 180,
        retries: int = 3,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.text_base_url = text_base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
        self.files_base_url = files_base_url.rstrip("/")
        self.text_model = text_model
        self.image_model = image_model
        self.timeout = timeout
        self.retries = retries
        self.opener = opener
        self.sleep = sleep

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotent: bool = True,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if request_id:
            headers["Idempotency-Key"] = request_id
        attempts = self.retries if idempotent else 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            request = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=method,
            )
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as exc:
                detail = _safe_error_body(
                    exc.read().decode("utf-8", errors="replace")
                )
                if exc.code == 401:
                    raise EvoLinkError(
                        "EvoLink 鉴权失败。请确认本地保存的是 EvoLink API Key；"
                        "旧 8AI 密钥不再受支持。"
                    ) from exc
                if exc.code == 402:
                    raise EvoLinkError("EvoLink 余额不足，请充值后使用 --resume 继续。") from exc
                if exc.code not in {429, 500, 502, 503} or attempt == attempts:
                    raise EvoLinkError(f"EvoLink HTTP {exc.code}：{detail}") from exc
                last_error = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == attempts:
                    raise EvoLinkError(f"EvoLink 网络请求失败：{exc}") from exc
                last_error = exc
            self.sleep(min(2**attempt, 8))
        raise EvoLinkError(str(last_error))

    def get_credits(self) -> dict[str, Any]:
        return self._request_json("GET", f"{self.api_base_url}/v1/credits")

    def generate_content(
        self,
        prompt: str,
        media_files: list[str | Path] | None = None,
        *,
        schema: dict[str, Any] | None = None,
        max_output_tokens: int = 16000,
        request_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        started = time.monotonic()
        payload = build_generate_content_payload(
            prompt,
            media_files,
            schema=schema,
            max_output_tokens=max_output_tokens,
        )
        url = (
            f"{self.text_base_url}/v1beta/models/"
            f"{self.text_model}:generateContent"
        )
        response = self._request_json(
            "POST",
            url,
            payload,
            idempotent=True,
            request_id=request_id,
        )
        text = extract_generated_text(response)
        trace = {
            "response_id": response.get("responseId"),
            "model": response.get("modelVersion") or self.text_model,
            "status": "completed",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "usage": response.get("usageMetadata", {}),
            "input_files": [Path(item).name for item in (media_files or [])],
            "output": text,
        }
        return text, trace

    def upload_image(self, path: str | Path) -> tuple[str, dict[str, Any]]:
        source = Path(path).expanduser().resolve()
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        if mime_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
            raise EvoLinkError(f"EvoLink 文件服务不支持该图片格式：{source.name}")
        data_url = (
            f"data:{mime_type};base64,"
            f"{base64.b64encode(source.read_bytes()).decode('ascii')}"
        )
        response = self._request_json(
            "POST",
            f"{self.files_base_url}/api/v1/files/upload/base64",
            {"base64_data": data_url, "file_name": source.name},
            idempotent=True,
        )
        data = response.get("data") or {}
        file_url = data.get("file_url")
        if not file_url:
            raise EvoLinkError("EvoLink 图片上传响应缺少 file_url。")
        return str(file_url), {
            "file_id": data.get("file_id"),
            "file_name": source.name,
            "expires_at": data.get("expires_at"),
        }

    def create_image_task(
        self,
        *,
        prompt: str,
        image_urls: list[str],
        quality: str,
        aspect_ratio: str,
        request_id: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.image_model,
            "prompt": limit_image_prompt(prompt),
            "size": aspect_ratio,
            "quality": quality,
        }
        if image_urls:
            payload["image_urls"] = image_urls
        return self._request_json(
            "POST",
            f"{self.api_base_url}/v1/images/generations",
            payload,
            idempotent=False,
            request_id=request_id,
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"{self.api_base_url}/v1/tasks/{task_id}",
        )

    @staticmethod
    def _write_task_state(
        path: Path,
        task: dict[str, Any],
        *,
        local_output: Path | None = None,
    ) -> None:
        state = {
            "task_id": task.get("id") or task.get("taskId"),
            "status": task.get("status", "pending"),
            "model": task.get("model", "gemini-3-pro-image-preview"),
            "progress": task.get("progress", 0),
            "usage": task.get("usage", {}),
        }
        if local_output is not None:
            state["local_output"] = str(local_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _result_url(task: dict[str, Any]) -> str:
        results = task.get("results") or task.get("result_list") or []
        if not results:
            raise EvoLinkError("EvoLink 图片任务已完成但没有结果。")
        first = results[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("url", "image_url", "file_url"):
                if first.get(key):
                    return str(first[key])
        raise EvoLinkError("EvoLink 图片任务结果中没有可下载地址。")

    def _download(self, url: str, output_path: Path) -> None:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            method="GET",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = response.read()
        except Exception as exc:
            raise EvoLinkError(f"生成图片下载失败：{exc}") from exc
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(body)

    def generate_image(
        self,
        *,
        prompt: str,
        reference_images: list[str | Path],
        reference_urls: list[str] | None = None,
        output_path: str | Path,
        state_path: str | Path,
        quality: str = "2K",
        aspect_ratio: str = "9:16",
        poll_interval: float = 3,
        poll_timeout: float = 600,
        request_id: str | None = None,
    ) -> Path:
        if quality not in {"1K", "2K"}:
            raise EvoLinkError("本流程仅允许显式选择 1K 或默认 2K。")
        output = Path(output_path).expanduser().resolve()
        state_file = Path(state_path).expanduser().resolve()
        state: dict[str, Any] = {}
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8-sig"))
            if state.get("status") == "completed" and output.exists():
                return output

        task_id = str(state.get("task_id") or "")
        if not task_id:
            image_urls = list(reference_urls or [])
            image_urls.extend(self.upload_image(path)[0] for path in reference_images)
            submitted = self.create_image_task(
                prompt=prompt,
                image_urls=image_urls,
                quality=quality,
                aspect_ratio=aspect_ratio,
                request_id=request_id or f"image-{int(time.time() * 1000)}",
            )
            task_id = str(submitted.get("id") or submitted.get("taskId") or "")
            if not task_id:
                raise EvoLinkError("EvoLink 生图响应缺少任务 ID。")
            submitted.setdefault("id", task_id)
            submitted.setdefault("status", "pending")
            self._write_task_state(state_file, submitted)

        deadline = time.monotonic() + poll_timeout
        while True:
            task = self.get_task(task_id)
            task.setdefault("id", task_id)
            self._write_task_state(state_file, task)
            status = str(task.get("status", "")).lower()
            if status == "completed":
                self._download(self._result_url(task), output)
                self._write_task_state(state_file, task, local_output=output)
                return output
            if status == "failed":
                error = task.get("error") or {}
                raise EvoLinkError(
                    f"EvoLink 图片任务失败：{_safe_error_body(json.dumps(error, ensure_ascii=False))}"
                )
            if time.monotonic() >= deadline:
                raise EvoLinkError(
                    f"EvoLink 图片任务轮询超时；任务 ID 已保存，可使用 --resume 继续：{task_id}"
                )
            self.sleep(poll_interval)

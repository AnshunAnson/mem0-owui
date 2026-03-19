"""OpenAI-compatible LLM client."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.config import Settings


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = self._build_url("/chat/completions")
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            raw = self._post_json(url, headers, payload)
        except error.HTTPError as exc:
            if exc.code not in {400, 404, 422}:
                raise
            payload.pop("response_format", None)
            raw = self._post_json(url, headers, payload)

        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        return self._loads_json(content)

    def readiness(self) -> tuple[bool, str]:
        url = self._build_url("/models")
        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        try:
            req = request.Request(url, headers=headers, method="GET")
            with request.urlopen(req, timeout=self.settings.llm_ready_timeout_seconds) as response:
                response.read()
            return True, f"reachable:{url}"
        except Exception as exc:
            return False, str(exc)

    def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=self.settings.llm_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_url(self, path: str) -> str:
        base = self.settings.llm_api_base.rstrip("/")
        if base.endswith(path):
            return base
        return f"{base}{path}"

    def _loads_json(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if isinstance(content, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        else:
            text = str(content)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}


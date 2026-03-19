"""
title: mem0-owui-thin
author: OpenAI Codex
date: 2026-03-19
version: 2.0
license: MIT
description: Thin OpenWebUI filter that delegates retrieval and memory events to the async governance control plane.
requirements: pydantic==2.11.4
"""

import asyncio
import json
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional
from urllib import request

from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = ["*"]
        priority: int = 0
        control_plane_base_url: str = "http://host.docker.internal:8081"
        control_plane_timeout_seconds: int = 5
        default_user_id: str = "default_user"
        default_project_id: str = "default"
        default_task_id: str = "default"

    def __init__(self):
        self.type = "filter"
        self.valves = self.Valves(**{"pipelines": ["*"]})

    async def on_startup(self):
        print(f"on_startup:{__name__}")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        user_message = self._latest_user_message(messages)
        if not user_message:
            return body

        scope = self._resolve_scope(user)
        try:
            retrieval = await asyncio.to_thread(self._fetch_retrieval, user_message, scope)
            injected_context = retrieval.get("injected_context", "").strip()
            if injected_context:
                system_message = next((msg for msg in messages if msg.get("role") == "system"), None)
                if system_message:
                    system_message["content"] = (
                        f"{self._stringify_content(system_message.get('content'))}\n\n{injected_context}"
                    ).strip()
                else:
                    messages.insert(0, {"role": "system", "content": injected_context})
                body["messages"] = messages
        except Exception as exc:
            print(f"mem0 inlet retrieval error: {exc}")

        body["_mem0_scope"] = scope
        body["_mem0_messages_snapshot"] = deepcopy(messages)
        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        scope = body.get("_mem0_scope") or self._resolve_scope(user)
        messages = deepcopy(body.get("_mem0_messages_snapshot") or body.get("messages", []))
        assistant_message = self._extract_assistant_message(body)
        if assistant_message:
            if not messages or messages[-1].get("role") != "assistant":
                messages.append(assistant_message)
            elif self._stringify_content(messages[-1].get("content")) != assistant_message["content"]:
                messages.append(assistant_message)

        if not assistant_message:
            return body

        payload = {
            "event_id": str(uuid.uuid4()),
            "conversation_id": body.get("chat_id") or body.get("conversation_id") or str(uuid.uuid4()),
            "user_id": scope["user_id"],
            "scope": scope,
            "messages": self._normalize_messages(messages),
            "assistant_response": assistant_message["content"],
            "source": "openwebui_pipeline",
            "event_schema_version": "1.0",
        }
        try:
            await asyncio.to_thread(self._post_event, payload)
        except Exception as exc:
            print(f"mem0 outlet event post error: {exc}")
        return body

    def _fetch_retrieval(self, query: str, scope: Dict[str, str]) -> Dict[str, Any]:
        return self._http_json("/internal/retrieval", {"query": query, "scope": scope})

    def _post_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._http_json("/memory/events", payload)

    def _http_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.valves.control_plane_base_url.rstrip('/')}{path}"
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.valves.control_plane_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _resolve_scope(self, user: Optional[dict]) -> Dict[str, str]:
        user_id = self.valves.default_user_id
        if user and user.get("id"):
            user_id = str(user["id"])
        return {
            "user_id": user_id,
            "project_id": self.valves.default_project_id,
            "task_id": self.valves.default_task_id,
        }

    def _latest_user_message(self, messages: List[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return self._stringify_content(msg.get("content"))
        return ""

    def _extract_assistant_message(self, body: dict) -> Optional[dict]:
        messages = body.get("messages", [])
        if messages and messages[-1].get("role") == "assistant":
            return {
                "role": "assistant",
                "content": self._stringify_content(messages[-1].get("content")),
            }

        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = self._stringify_content(message.get("content"))
            if content:
                return {"role": "assistant", "content": content}

        response_text = self._stringify_content(
            body.get("response") or body.get("output") or body.get("content")
        )
        if response_text:
            return {"role": "assistant", "content": response_text}
        return None

    def _normalize_messages(self, messages: List[dict]) -> List[Dict[str, str]]:
        normalized = []
        for msg in messages:
            role = msg.get("role")
            content = self._stringify_content(msg.get("content"))
            if role and content:
                normalized.append({"role": role, "content": content})
        return normalized

    def _stringify_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif "text" in item:
                        parts.append(str(item["text"]))
                elif item is not None:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        if content is None:
            return ""
        return str(content)

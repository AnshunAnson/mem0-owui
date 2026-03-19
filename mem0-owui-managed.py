"""
title: mem0-owui
author: Vederis Leunardus
date: 2025-05-03
version: 1.1
license: MIT
description: Filter that works with mem0
requirements: mem0ai, pydantic==2.11.4
"""

import asyncio
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional
from urllib import error, request

from mem0 import MemoryClient
from pydantic import BaseModel, Field


class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = ["*"]
        priority: int = 0
        api_key: str = Field(
            default="put_api_key_here",
            description="mem0 API key for authentication. Must be set in OpenWebUI dashboard.",
        )
        user_id: str = "default_user"
        llm_api_base: str = "http://host.docker.internal:1234/v1"
        llm_api_key: str = ""
        llm_model: str = "gpt-4o-mini"
        llm_timeout: int = 30
        memory_confidence_threshold: float = 0.7
        memory_search_limit: int = 5

    def __init__(self):
        self.type = "filter"
        self.valves = self.Valves(**{"pipelines": ["*"]})
        self.memory = None

    async def on_startup(self):
        print(f"on_startup:{__name__}")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        current_user_id = self._resolve_user_id(user)
        user_message = self._latest_user_message(messages)
        if not user_message:
            return body

        try:
            memories = await asyncio.to_thread(
                self.search_memories,
                user_message,
                current_user_id,
                self.valves.memory_search_limit,
            )
            memory_context = self._build_memory_context(memories)
            if memory_context:
                system_message = next((msg for msg in messages if msg.get("role") == "system"), None)
                if system_message:
                    system_message["content"] = f"{self._stringify_content(system_message.get('content'))}{memory_context}"
                else:
                    messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": f"Use these memories to enhance your response:{memory_context}",
                        },
                    )
                body["messages"] = messages
        except Exception as exc:
            print(f"Mem0 retrieval error: {exc}")

        body["_mem0_user_id"] = current_user_id
        body["_mem0_messages_snapshot"] = deepcopy(messages)
        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        current_user_id = body.get("_mem0_user_id") or self._resolve_user_id(user)
        messages = deepcopy(body.get("_mem0_messages_snapshot") or body.get("messages", []))
        assistant_message = self._extract_assistant_message(body)
        if assistant_message:
            if not messages or messages[-1].get("role") != "assistant":
                messages.append(assistant_message)
            elif self._stringify_content(messages[-1].get("content")) != assistant_message["content"]:
                messages.append(assistant_message)

        asyncio.create_task(self._persist_evolved_memory(messages, current_user_id))
        return body

    def extract_memory(self, messages: List[dict]) -> Dict[str, Any]:
        prompt = (
            "你是一个经验提炼系统。\n"
            "从对话中提取长期有用的记忆。\n\n"
            "分类：\n"
            "* preference\n"
            "* correction\n"
            "* routine\n"
            "* fact\n"
            "* noise\n\n"
            "要求：\n"
            "* 输出简洁规则\n"
            "* 去除一次性信息\n\n"
            "输出JSON。\n"
            "只返回如下结构：\n"
            '{"type":"preference|correction|routine|fact|noise","content":"...","confidence":0.0,"tags":[]}'
        )
        conversation = json.dumps(self._normalize_messages(messages), ensure_ascii=False, indent=2)
        result = self._chat_json(
            system_prompt=prompt,
            user_prompt=f"对话内容：\n{conversation}",
        )
        memory = {
            "type": result.get("type", "noise"),
            "content": result.get("content", ""),
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "tags": result.get("tags", []) or [],
        }
        if not memory["content"]:
            memory["type"] = "noise"
            memory["confidence"] = 0.0
        return memory

    def evolve_memory(self, existing_memories: Any, new_memory: Dict[str, Any]) -> Dict[str, Any]:
        normalized_existing = self._normalize_memories(existing_memories)
        prompt = (
            "你是一个记忆进化系统。\n\n"
            f"已有记忆：\n{json.dumps(normalized_existing, ensure_ascii=False, indent=2)}\n\n"
            f"新记忆：\n{json.dumps(new_memory, ensure_ascii=False, indent=2)}\n\n"
            "决策：\n"
            "* add\n"
            "* update\n"
            "* merge\n"
            "* link\n"
            "* discard\n\n"
            "规则：\n"
            "* 重复 -> discard\n"
            "* 更准确 -> update\n"
            "* 补充 -> merge\n"
            "* 相关 -> link\n"
            "* 新 -> add\n\n"
            "输出JSON。\n"
            '只返回如下结构：{"action":"add|update|merge|link|discard","target_id":"","memory":"","relations":[]}'
        )
        result = self._chat_json(
            system_prompt="你是一个记忆进化系统，只返回JSON。",
            user_prompt=prompt,
        )
        action = result.get("action", "discard")
        if action not in {"add", "update", "merge", "link", "discard"}:
            action = "discard"
        target_id = result.get("target_id") or self._best_target_id(normalized_existing)
        memory_text = result.get("memory") or new_memory.get("content", "")
        relations = result.get("relations", []) or []
        return {
            "action": action,
            "target_id": target_id,
            "memory": memory_text,
            "relations": relations,
            "new_memory": new_memory,
        }

    def apply_memory_action(self, action_result: Dict[str, Any]) -> None:
        action = action_result.get("action", "discard")
        if action == "discard":
            return

        memory_text = action_result.get("memory") or action_result.get("new_memory", {}).get("content", "")
        if not memory_text:
            return

        user_id = action_result.get("user_id") or self.valves.user_id
        metadata = {
            "type": action_result.get("new_memory", {}).get("type"),
            "confidence": action_result.get("new_memory", {}).get("confidence"),
            "tags": action_result.get("new_memory", {}).get("tags", []),
            "relations": action_result.get("relations", []),
            "evolution_action": action,
        }

        if action in {"add", "link"}:
            self.add_memory(memory_text, user_id, metadata)
            return

        if action in {"update", "merge"} and action_result.get("target_id"):
            self.update_memory(action_result["target_id"], memory_text, metadata)
            return

        self.add_memory(memory_text, user_id, metadata)

    async def _persist_evolved_memory(self, messages: List[dict], current_user_id: str) -> None:
        if not messages:
            return

        try:
            new_memory = await asyncio.to_thread(self.extract_memory, messages)
            if (
                new_memory["type"] == "noise"
                or new_memory["confidence"] <= self.valves.memory_confidence_threshold
            ):
                return

            existing = await asyncio.to_thread(
                self.search_memories,
                new_memory["content"],
                current_user_id,
                self.valves.memory_search_limit,
            )
            decision = await asyncio.to_thread(self.evolve_memory, existing, new_memory)
            decision["user_id"] = current_user_id
            await asyncio.to_thread(self.apply_memory_action, decision)
        except Exception as exc:
            print(f"Mem0 evolution error: {exc}")

    def _ensure_memory(self):
        if self.memory is not None:
            return self.memory

        try:
            self.memory = MemoryClient(api_key=self.valves.api_key, enable_graph=True)
        except TypeError:
            self.memory = MemoryClient(api_key=self.valves.api_key)
        return self.memory

    def search_memories(self, query: str, user_id: str, limit: int = 5) -> Any:
        memory = self._ensure_memory()
        attempts = [
            lambda: memory.search(query=query, user_id=user_id, limit=limit),
            lambda: memory.search(query, user_id=user_id, limit=limit),
            lambda: memory.search(query=query, filters={"user_id": user_id}, limit=limit),
            lambda: memory.search(query, filters={"user_id": user_id}, limit=limit),
        ]
        last_error = None
        for call in attempts:
            try:
                return call()
            except TypeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return []

    def add_memory(self, text: str, user_id: str, metadata: Dict[str, Any]) -> Any:
        memory = self._ensure_memory()
        messages = [{"role": "user", "content": text}]
        attempts = [
            lambda: memory.add(messages=messages, user_id=user_id, metadata=metadata, infer=False),
            lambda: memory.add(messages=messages, user_id=user_id, metadata=metadata),
            lambda: memory.add(messages, user_id=user_id, metadata=metadata, infer=False),
            lambda: memory.add(messages, user_id=user_id, metadata=metadata),
            lambda: memory.add(messages=messages, user_id=user_id),
        ]
        last_error = None
        for call in attempts:
            try:
                return call()
            except TypeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return None

    def update_memory(self, memory_id: str, text: str, metadata: Dict[str, Any]) -> Any:
        memory = self._ensure_memory()
        attempts = [
            lambda: memory.update(memory_id=memory_id, text=text, metadata=metadata),
            lambda: memory.update(memory_id=memory_id, data=text, metadata=metadata),
            lambda: memory.update(memory_id, text=text, metadata=metadata),
            lambda: memory.update(memory_id, data=text, metadata=metadata),
        ]
        last_error = None
        for call in attempts:
            try:
                return call()
            except TypeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return None

    def _chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.valves.llm_api_base or not self.valves.llm_model:
            return {}

        url = self._build_chat_url(self.valves.llm_api_base)
        headers = {"Content-Type": "application/json"}
        if self.valves.llm_api_key:
            headers["Authorization"] = f"Bearer {self.valves.llm_api_key}"

        payload = {
            "model": self.valves.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            raw = self._http_post_json(url, headers, payload)
        except error.HTTPError as exc:
            if exc.code not in {400, 404, 422}:
                raise
            payload.pop("response_format", None)
            raw = self._http_post_json(url, headers, payload)

        content = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        return self._loads_json(content)

    def _http_post_json(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=self.valves.llm_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_chat_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _loads_json(self, content: Any) -> Dict[str, Any]:
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

    def _normalize_memories(self, memories: Any) -> List[Dict[str, Any]]:
        if isinstance(memories, dict):
            if "results" in memories and isinstance(memories["results"], list):
                items = memories["results"]
            elif "memories" in memories and isinstance(memories["memories"], list):
                items = memories["memories"]
            else:
                items = []
        elif isinstance(memories, list):
            items = memories
        else:
            items = []

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("id") or item.get("memory_id"),
                    "memory": item.get("memory") or item.get("text") or item.get("content"),
                    "score": item.get("score"),
                    "metadata": item.get("metadata", {}),
                }
            )
        return normalized

    def _best_target_id(self, memories: List[Dict[str, Any]]) -> str:
        for item in memories:
            if item.get("id"):
                return item["id"]
        return ""

    def _build_memory_context(self, memories: Any) -> str:
        items = self._normalize_memories(memories)
        if not items:
            return ""
        lines = [f"- {item['memory']}" for item in items if item.get("memory")]
        if not lines:
            return ""
        return "\n\nRelevant memories:\n" + "\n".join(lines)

    def _resolve_user_id(self, user: Optional[dict]) -> str:
        if user and "id" in user:
            return user["id"]
        return self.valves.user_id

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
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        if content is None:
            return ""
        return str(content)

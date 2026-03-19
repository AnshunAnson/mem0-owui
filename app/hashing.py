"""Stable hashing helpers for events and applies."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return value.strip()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(normalize_value(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_time_bucket(when: datetime, window_seconds: int) -> int:
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    epoch = int(when.timestamp())
    return epoch // window_seconds


def build_dedupe_key(
    *,
    conversation_id: str,
    messages: list[dict[str, Any]],
    assistant_response: str,
    scope: dict[str, Any],
    source: str,
    window_seconds: int,
    when: datetime,
) -> str:
    payload = {
        "conversation_id": conversation_id,
        "messages": messages,
        "assistant_response": assistant_response,
        "scope": scope,
        "source": source,
        "time_bucket": compute_time_bucket(when, window_seconds),
    }
    return sha256_text(canonical_json(payload))


def build_candidate_hash(candidate: dict[str, Any]) -> str:
    payload = {
        "action": candidate.get("action"),
        "target_id": candidate.get("target_id"),
        "memory": candidate.get("memory"),
        "relations": candidate.get("relations", []),
        "reason": candidate.get("reason"),
        "memory_kind": candidate.get("memory_kind"),
        "confidence": candidate.get("confidence"),
    }
    return sha256_text(canonical_json(payload))


def build_apply_id(event_id: str, candidate_hash: str, final_action: str, target_id: str | None) -> str:
    payload = {
        "event_id": event_id,
        "candidate_hash": candidate_hash,
        "final_action": final_action,
        "target_id": target_id or "",
    }
    return sha256_text(canonical_json(payload))


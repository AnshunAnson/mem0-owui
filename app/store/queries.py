"""Ledger CRUD operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app import constants
from app.config import Settings
from app.schemas.events import MemoryEventFilters
from app.state_machine import ensure_transition
from app.store.sqlite import connect, transaction


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime | None = None) -> str:
    if value is None:
        value = _utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def create_event(
    settings: Settings,
    *,
    event_id: str,
    dedupe_key: str,
    conversation_id: str,
    user_id: str,
    scope: dict[str, Any],
    payload: dict[str, Any],
    status: str,
    event_schema_version: str,
) -> dict[str, Any]:
    timestamp = _isoformat()
    with transaction(settings) as connection:
        connection.execute(
            """
            INSERT INTO memory_events (
                event_id, dedupe_key, conversation_id, user_id, scope_json,
                payload_json, status, event_schema_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                dedupe_key,
                conversation_id,
                user_id,
                json.dumps(scope, ensure_ascii=True, sort_keys=True),
                json.dumps(payload, ensure_ascii=True, sort_keys=True),
                status,
                event_schema_version,
                timestamp,
                timestamp,
            ),
        )
    return get_event(settings, event_id)


def get_event(settings: Settings, event_id: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT event_id, dedupe_key, conversation_id, user_id, scope_json, payload_json,
                   status, event_schema_version, retry_count, last_error, next_retry_at,
                   dead_lettered_at, created_at, updated_at
            FROM memory_events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_event_row(row)


def get_event_by_dedupe_key(settings: Settings, dedupe_key: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT event_id, dedupe_key, conversation_id, user_id, scope_json, payload_json,
                   status, event_schema_version, retry_count, last_error, next_retry_at,
                   dead_lettered_at, created_at, updated_at
            FROM memory_events
            WHERE dedupe_key = ?
            """,
            (dedupe_key,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_event_row(row)


def list_events(settings: Settings, filters: MemoryEventFilters) -> tuple[list[dict[str, Any]], int]:
    where_clauses: list[str] = []
    parameters: list[Any] = []

    if filters.status:
        where_clauses.append("status = ?")
        parameters.append(filters.status)
    if filters.user_id:
        where_clauses.append("user_id = ?")
        parameters.append(filters.user_id)
    if filters.conversation_id:
        where_clauses.append("conversation_id = ?")
        parameters.append(filters.conversation_id)
    if filters.scope_project_id:
        where_clauses.append("json_extract(scope_json, '$.project_id') = ?")
        parameters.append(filters.scope_project_id)
    if filters.scope_task_id:
        where_clauses.append("json_extract(scope_json, '$.task_id') = ?")
        parameters.append(filters.scope_task_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    count_sql = f"SELECT COUNT(*) AS total FROM memory_events {where_sql}"
    query_sql = f"""
        SELECT event_id, dedupe_key, conversation_id, user_id, scope_json, payload_json,
               status, event_schema_version, retry_count, last_error, next_retry_at,
               dead_lettered_at, created_at, updated_at
        FROM memory_events
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """

    connection = connect(settings)
    try:
        total_row = connection.execute(count_sql, tuple(parameters)).fetchone()
        rows = connection.execute(query_sql, tuple(parameters + [filters.limit, filters.offset])).fetchall()
    finally:
        connection.close()

    items = [_decode_event_row(row) for row in rows]
    total = int(total_row["total"]) if total_row else 0
    return items, total


def update_event_status(
    settings: Settings,
    event_id: str,
    next_status: str,
    *,
    last_error: str | None = None,
    increment_retry: bool = False,
    next_retry_at: datetime | None = None,
    dead_lettered_at: datetime | None = None,
) -> dict[str, Any]:
    current = get_event(settings, event_id)
    if current is None:
        raise KeyError(f"Event not found: {event_id}")
    ensure_transition(current["status"], next_status)

    retry_count = current["retry_count"] + (1 if increment_retry else 0)
    with transaction(settings) as connection:
        connection.execute(
            """
            UPDATE memory_events
            SET status = ?, retry_count = ?, last_error = ?, next_retry_at = ?,
                dead_lettered_at = ?, updated_at = ?
            WHERE event_id = ?
            """,
            (
                next_status,
                retry_count,
                last_error,
                _isoformat(next_retry_at) if next_retry_at else None,
                _isoformat(dead_lettered_at) if dead_lettered_at else None,
                _isoformat(),
                event_id,
            ),
        )
    return get_event(settings, event_id)


def force_update_event_status(
    settings: Settings,
    event_id: str,
    next_status: str,
    *,
    last_error: str | None = None,
    next_retry_at: datetime | None = None,
    dead_lettered_at: datetime | None = None,
) -> dict[str, Any]:
    with transaction(settings) as connection:
        connection.execute(
            """
            UPDATE memory_events
            SET status = ?, last_error = ?, next_retry_at = ?, dead_lettered_at = ?, updated_at = ?
            WHERE event_id = ?
            """,
            (
                next_status,
                last_error,
                _isoformat(next_retry_at) if next_retry_at else None,
                _isoformat(dead_lettered_at) if dead_lettered_at else None,
                _isoformat(),
                event_id,
            ),
        )
    return get_event(settings, event_id)


def mark_event_terminal_failure(settings: Settings, event_id: str, last_error: str) -> dict[str, Any]:
    current = get_event(settings, event_id)
    if current is None:
        raise KeyError(f"Event not found: {event_id}")
    if current["status"] == constants.STATUS_QUEUE_FAILED:
        next_status = constants.STATUS_FAILED
    elif current["status"] == constants.STATUS_APPLYING:
        next_status = constants.STATUS_FAILED
    elif current["status"] == constants.STATUS_EXTRACTING:
        next_status = constants.STATUS_FAILED
    else:
        next_status = constants.STATUS_FAILED
    with transaction(settings) as connection:
        connection.execute(
            """
            UPDATE memory_events
            SET status = ?, last_error = ?, updated_at = ?, dead_lettered_at = ?
            WHERE event_id = ?
            """,
            (next_status, last_error, _isoformat(), _isoformat(), event_id),
        )
    return get_event(settings, event_id)


def schedule_retry(settings: Settings, event_id: str, last_error: str, delay_seconds: int) -> dict[str, Any]:
    current = get_event(settings, event_id)
    if current is None:
        raise KeyError(f"Event not found: {event_id}")
    next_retry = _utcnow() + timedelta(seconds=delay_seconds)
    if current["status"] not in (constants.STATUS_RECEIVED, constants.STATUS_QUEUE_FAILED):
        next_status = constants.STATUS_FAILED
        with transaction(settings) as connection:
            connection.execute(
                """
                UPDATE memory_events
                SET status = ?, retry_count = ?, last_error = ?, next_retry_at = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (
                    next_status,
                    current["retry_count"] + 1,
                    last_error,
                    _isoformat(next_retry),
                    _isoformat(),
                    event_id,
                ),
            )
        return get_event(settings, event_id)
    return update_event_status(
        settings,
        event_id,
        constants.STATUS_QUEUE_FAILED,
        last_error=last_error,
        increment_retry=True,
        next_retry_at=next_retry,
    )


def get_retryable_events(settings: Settings, *, statuses: tuple[str, ...], limit: int = 100) -> list[dict[str, Any]]:
    now = _isoformat()
    placeholders = ",".join("?" for _ in statuses)
    connection = connect(settings)
    try:
        rows = connection.execute(
            f"""
            SELECT event_id, dedupe_key, conversation_id, user_id, scope_json, payload_json,
                   status, event_schema_version, retry_count, last_error, next_retry_at,
                   dead_lettered_at, created_at, updated_at
            FROM memory_events
            WHERE status IN ({placeholders})
              AND (next_retry_at IS NULL OR next_retry_at <= ?)
              AND dead_lettered_at IS NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            tuple(statuses) + (now, limit),
        ).fetchall()
    finally:
        connection.close()
    return [_decode_event_row(row) for row in rows]


def get_next_candidate_version(settings: Settings, event_id: str) -> int:
    connection = connect(settings)
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(candidate_version), 0) AS max_version FROM memory_candidates WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    finally:
        connection.close()
    return int(row["max_version"]) + 1


def insert_candidate(
    settings: Settings,
    *,
    candidate_id: str,
    event_id: str,
    candidate_version: int,
    candidate_hash: str,
    candidate: dict[str, Any],
    candidate_schema_version: str,
) -> dict[str, Any]:
    created_at = _isoformat()
    with transaction(settings) as connection:
        connection.execute(
            """
            INSERT INTO memory_candidates (
                candidate_id, event_id, candidate_version, candidate_hash,
                candidate_json, candidate_schema_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                event_id,
                candidate_version,
                candidate_hash,
                json.dumps(candidate, ensure_ascii=True, sort_keys=True),
                candidate_schema_version,
                created_at,
            ),
        )
    return get_latest_candidate(settings, event_id)


def get_latest_candidate(settings: Settings, event_id: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT candidate_id, event_id, candidate_version, candidate_hash, candidate_json,
                   candidate_schema_version, created_at
            FROM memory_candidates
            WHERE event_id = ?
            ORDER BY candidate_version DESC
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_candidate_row(row)


def insert_audit(
    settings: Settings,
    *,
    audit_id: str,
    event_id: str,
    candidate_id: str,
    audit_result: str,
    audit_payload: dict[str, Any],
    audit_schema_version: str,
) -> dict[str, Any]:
    created_at = _isoformat()
    with transaction(settings) as connection:
        connection.execute(
            """
            INSERT INTO memory_audits (
                audit_id, event_id, candidate_id, audit_result,
                audit_json, audit_schema_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                event_id,
                candidate_id,
                audit_result,
                json.dumps(audit_payload, ensure_ascii=True, sort_keys=True),
                audit_schema_version,
                created_at,
            ),
        )
    return get_latest_audit(settings, event_id)


def get_latest_audit(settings: Settings, event_id: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT audit_id, event_id, candidate_id, audit_result, audit_json,
                   audit_schema_version, created_at
            FROM memory_audits
            WHERE event_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_audit_row(row)


def insert_apply(
    settings: Settings,
    *,
    apply_id: str,
    event_id: str,
    candidate_id: str,
    final_action: str,
    target_id: str | None,
    mem0_memory_id: str | None,
    apply_status: str,
    graph_degraded: bool,
) -> dict[str, Any]:
    created_at = _isoformat()
    with transaction(settings) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO memory_applies (
                apply_id, event_id, candidate_id, final_action, target_id,
                mem0_memory_id, apply_status, graph_degraded, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                apply_id,
                event_id,
                candidate_id,
                final_action,
                target_id,
                mem0_memory_id,
                apply_status,
                int(graph_degraded),
                created_at,
            ),
        )
    return get_apply(settings, apply_id)


def get_apply(settings: Settings, apply_id: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT apply_id, event_id, candidate_id, final_action, target_id,
                   mem0_memory_id, apply_status, graph_degraded, created_at
            FROM memory_applies
            WHERE apply_id = ?
            """,
            (apply_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_apply_row(row)


def get_latest_apply(settings: Settings, event_id: str) -> dict[str, Any] | None:
    connection = connect(settings)
    try:
        row = connection.execute(
            """
            SELECT apply_id, event_id, candidate_id, final_action, target_id,
                   mem0_memory_id, apply_status, graph_degraded, created_at
            FROM memory_applies
            WHERE event_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return _decode_apply_row(row)


def build_timeline(settings: Settings, event_id: str) -> list[dict[str, Any]]:
    event = get_event(settings, event_id)
    timeline: list[dict[str, Any]] = []
    if event:
        timeline.append({"step": "event", "status": event["status"], "created_at": event["created_at"]})
    candidate = get_latest_candidate(settings, event_id)
    if candidate:
        timeline.append({"step": "candidate", "status": constants.STATUS_CANDIDATE_READY, "created_at": candidate["created_at"]})
    audit = get_latest_audit(settings, event_id)
    if audit:
        timeline.append({"step": "audit", "status": audit["audit_result"], "created_at": audit["created_at"]})
    apply = get_latest_apply(settings, event_id)
    if apply:
        timeline.append({"step": "apply", "status": apply["apply_status"], "created_at": apply["created_at"]})
    return timeline


def _decode_event_row(row: Any) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "dedupe_key": row["dedupe_key"],
        "conversation_id": row["conversation_id"],
        "user_id": row["user_id"],
        "scope": json.loads(row["scope_json"]),
        "payload": json.loads(row["payload_json"]),
        "status": row["status"],
        "event_schema_version": row["event_schema_version"],
        "retry_count": int(row["retry_count"]),
        "last_error": row["last_error"],
        "next_retry_at": row["next_retry_at"],
        "dead_lettered_at": row["dead_lettered_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _decode_candidate_row(row: Any) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "event_id": row["event_id"],
        "candidate_version": int(row["candidate_version"]),
        "candidate_hash": row["candidate_hash"],
        "candidate": json.loads(row["candidate_json"]),
        "candidate_schema_version": row["candidate_schema_version"],
        "created_at": row["created_at"],
    }


def _decode_audit_row(row: Any) -> dict[str, Any]:
    return {
        "audit_id": row["audit_id"],
        "event_id": row["event_id"],
        "candidate_id": row["candidate_id"],
        "audit_result": row["audit_result"],
        "audit": json.loads(row["audit_json"]),
        "audit_schema_version": row["audit_schema_version"],
        "created_at": row["created_at"],
    }


def _decode_apply_row(row: Any) -> dict[str, Any]:
    return {
        "apply_id": row["apply_id"],
        "event_id": row["event_id"],
        "candidate_id": row["candidate_id"],
        "final_action": row["final_action"],
        "target_id": row["target_id"],
        "mem0_memory_id": row["mem0_memory_id"],
        "apply_status": row["apply_status"],
        "graph_degraded": bool(row["graph_degraded"]),
        "created_at": row["created_at"],
    }

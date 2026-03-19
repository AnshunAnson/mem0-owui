"""Event state transition rules."""

from __future__ import annotations

from app import constants


ALLOWED_TRANSITIONS = {
    constants.STATUS_RECEIVED: {constants.STATUS_QUEUED, constants.STATUS_QUEUE_FAILED},
    constants.STATUS_QUEUE_FAILED: {constants.STATUS_QUEUED, constants.STATUS_FAILED},
    constants.STATUS_QUEUED: {constants.STATUS_EXTRACTING},
    constants.STATUS_EXTRACTING: {constants.STATUS_CANDIDATE_READY, constants.STATUS_FAILED},
    constants.STATUS_CANDIDATE_READY: {constants.STATUS_AUDITING},
    constants.STATUS_AUDITING: {
        constants.STATUS_APPROVED,
        constants.STATUS_REVISED,
        constants.STATUS_REJECTED,
    },
    constants.STATUS_APPROVED: {constants.STATUS_APPLYING},
    constants.STATUS_REVISED: {constants.STATUS_APPLYING},
    constants.STATUS_REJECTED: {constants.STATUS_DISCARDED},
    constants.STATUS_APPLYING: {constants.STATUS_APPLIED, constants.STATUS_FAILED},
    constants.STATUS_APPLIED: set(),
    constants.STATUS_DISCARDED: set(),
    constants.STATUS_FAILED: set(),
}


def can_transition(current_status: str, next_status: str) -> bool:
    return next_status in ALLOWED_TRANSITIONS.get(current_status, set())


def ensure_transition(current_status: str, next_status: str) -> None:
    if current_status == next_status:
        return
    if not can_transition(current_status, next_status):
        raise ValueError(f"Invalid state transition: {current_status} -> {next_status}")


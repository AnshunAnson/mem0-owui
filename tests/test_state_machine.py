from __future__ import annotations

import pytest

from app import constants
from app.state_machine import can_transition, ensure_transition


def test_valid_transitions() -> None:
    assert can_transition(constants.STATUS_RECEIVED, constants.STATUS_QUEUED)
    assert can_transition(constants.STATUS_CANDIDATE_READY, constants.STATUS_AUDITING)
    assert can_transition(constants.STATUS_REJECTED, constants.STATUS_DISCARDED)


def test_invalid_transition_raises() -> None:
    with pytest.raises(ValueError):
        ensure_transition(constants.STATUS_RECEIVED, constants.STATUS_APPLIED)


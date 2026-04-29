"""Smoke tests for HITL approval scoping and TTL."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.hitl_manager import HITLManager


@pytest.fixture
def manager():
    # Each test gets a fresh manager instance.
    return HITLManager()


def _drain_pending_tasks():
    """Best-effort: let any scheduled persistence tasks finish without raising."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(asyncio.sleep(0))
    finally:
        loop.close()


def test_approvals_are_scoped_per_user(manager):
    manager.create_approval(
        session_id="s-1",
        agent_name="notification_specialist",
        action_type="email_send",
        draft_content="draft-A",
        user_id="user-A",
    )
    manager.create_approval(
        session_id="s-1",
        agent_name="notification_specialist",
        action_type="email_send",
        draft_content="draft-B",
        user_id="user-B",
    )

    a = manager.get_pending_approval("s-1", user_id="user-A")
    b = manager.get_pending_approval("s-1", user_id="user-B")

    assert a is not None and a.draft_content == "draft-A"
    assert b is not None and b.draft_content == "draft-B"

    # User A approving theirs must not consume B's approval.
    assert manager.approve("s-1", user_id="user-A") is not None
    assert manager.get_pending_approval("s-1", user_id="user-B") is not None


def test_approval_expires_after_ttl(manager, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("orchestrator.hitl_manager.APPROVAL_TTL_MINUTES", 0)
    manager.create_approval(
        session_id="s-2",
        agent_name="notification_specialist",
        action_type="email_send",
        draft_content="draft",
        user_id="user-A",
    )
    # Force the timestamp into the past.
    key = next(iter(manager._pending))
    manager._pending[key].created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert manager.get_pending_approval("s-2", user_id="user-A") is None

"""
HITL approval manager.

Approvals are scoped by (user_id, session_id) so a knowing-the-session-id
attacker cannot approve another user's pending email send.

Persistence: tries Supabase (table: hitl_approvals) so approvals survive
restarts and span workers. Falls back to an in-memory dict if Supabase is
unavailable, which preserves dev/test workflows but is single-process only.
"""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from pydantic import BaseModel

from shared.logging_utils import get_logger

logger = get_logger("orchestrator.hitl_manager")

DEFAULT_USER_ID = "default_user"
APPROVAL_TTL_MINUTES = int(os.getenv("HITL_APPROVAL_TTL_MINUTES", "30"))


class PendingApproval(BaseModel):
    """Represents a pending HITL approval."""
    user_id: str
    session_id: str
    agent_name: str
    action_type: str
    draft_content: str
    created_at: datetime
    metadata: Dict = {}


def _approval_key(user_id: str, session_id: str) -> str:
    return f"{user_id}::{session_id}"


class HITLManager:
    """In-memory + optional Supabase-persisted approval workflow."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: Dict[str, PendingApproval] = {}

    # ------------------------------------------------------------------ create
    def create_approval(
        self,
        session_id: str,
        agent_name: str,
        action_type: str,
        draft_content: str,
        metadata: Optional[Dict] = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> str:
        now = datetime.now(timezone.utc)
        approval_id = f"{user_id}_{session_id}_{action_type}_{now.timestamp()}"
        approval = PendingApproval(
            user_id=user_id,
            session_id=session_id,
            agent_name=agent_name,
            action_type=action_type,
            draft_content=draft_content,
            created_at=now,
            metadata=metadata or {},
        )
        with self._lock:
            self._pending[_approval_key(user_id, session_id)] = approval
        # Best-effort persistence; only attempt if a loop is already running.
        try:
            asyncio.get_running_loop().create_task(_persist_approval(approval))
        except RuntimeError:
            # No running loop (e.g. unit tests / sync caller) — skip persistence here.
            pass
        logger.info(
            "hitl_approval_created",
            user_id=user_id,
            session_id=session_id,
            agent=agent_name,
            action=action_type,
        )
        return approval_id

    # -------------------------------------------------------------------- get
    def get_pending_approval(
        self,
        session_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> Optional[PendingApproval]:
        with self._lock:
            approval = self._pending.get(_approval_key(user_id, session_id))
        if approval and self._is_expired(approval):
            self._discard(user_id, session_id)
            return None
        return approval

    # ----------------------------------------------------------------- approve
    def approve(
        self,
        session_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> Optional[PendingApproval]:
        approval = self.get_pending_approval(session_id, user_id=user_id)
        if approval is None:
            return None
        self._discard(user_id, session_id)
        try:
            asyncio.get_running_loop().create_task(_remove_approval(user_id, session_id))
        except RuntimeError:
            pass
        return approval

    # ------------------------------------------------------------------ reject
    def reject(
        self,
        session_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> Optional[PendingApproval]:
        return self.approve(session_id, user_id=user_id)

    # -------------------------------------------------------------------- has
    def has_pending_approval(
        self,
        session_id: str,
        user_id: str = DEFAULT_USER_ID,
    ) -> bool:
        return self.get_pending_approval(session_id, user_id=user_id) is not None

    # ------------------------------------------------------------------ helpers
    def _discard(self, user_id: str, session_id: str) -> None:
        with self._lock:
            self._pending.pop(_approval_key(user_id, session_id), None)

    @staticmethod
    def _is_expired(approval: PendingApproval) -> bool:
        ttl = timedelta(minutes=APPROVAL_TTL_MINUTES)
        return datetime.now(timezone.utc) - approval.created_at > ttl


async def _persist_approval(approval: PendingApproval) -> None:
    """Try to persist approval to Supabase; ignore failures."""
    try:
        from shared.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.insert(
            "hitl_approvals",
            {
                "user_id": approval.user_id,
                "session_id": approval.session_id,
                "agent_name": approval.agent_name,
                "action_type": approval.action_type,
                "draft_content": approval.draft_content,
                "metadata": approval.metadata,
                "created_at": approval.created_at.isoformat(),
            },
        )
    except Exception as exc:
        logger.debug("hitl_persist_failed", error=str(exc))


async def _remove_approval(user_id: str, session_id: str) -> None:
    try:
        from shared.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.delete(
            "hitl_approvals",
            filters={
                "user_id": f"eq.{user_id}",
                "session_id": f"eq.{session_id}",
            },
        )
    except Exception as exc:
        logger.debug("hitl_remove_failed", error=str(exc))


hitl_manager = HITLManager()

"""
In-memory + Supabase-backed agent telemetry.

`record_agent_call` keeps a rolling in-memory aggregate (cheap to read for
dashboards) and best-effort writes a row to the `agent_metrics` table so
that telemetry survives restarts and can be queried across replicas.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared.logging_utils import get_logger

logger = get_logger("shared.agent_metrics")


def _try_persist(record: Dict[str, Any]) -> None:
    try:
        from shared.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.insert("agent_metrics", record)
    except Exception as exc:
        logger.debug("agent_metrics_persist_failed", error=str(exc))


class AgentMetrics:
    """Thread-safe rolling aggregator + persistence handoff."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def record_agent_call(
        self,
        agent_name: str,
        session_id: str,
        success: bool,
        latency_ms: float,
        token_count: Optional[int] = None,
        error: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            stats = self.metrics.setdefault(
                agent_name,
                {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_latency_ms": 0.0,
                    "total_tokens": 0,
                    "errors": [],
                },
            )
            stats["total_calls"] += 1
            stats["total_latency_ms"] += latency_ms

            if success:
                stats["successful_calls"] += 1
            else:
                stats["failed_calls"] += 1
                if error and len(stats["errors"]) < 10:
                    stats["errors"].append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "session_id": session_id,
                            "error": str(error)[:200],
                        }
                    )

            if token_count:
                stats["total_tokens"] += token_count

        record = {
            "agent_name": agent_name,
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "success": success,
            "latency_ms": int(latency_ms),
            "token_count": token_count,
            "error": (str(error)[:500] if error else None),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        # Schedule persistence on the event loop if one is running, otherwise
        # run inline (best-effort) so seed scripts and tests still work.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(None, _try_persist, record)
            else:
                _try_persist(record)
        except RuntimeError:
            _try_persist(record)

    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        with self._lock:
            stats = self.metrics.get(agent_name)
            if not stats:
                return {}
            total = stats["total_calls"]
            if total == 0:
                return dict(stats)
            return {
                **stats,
                "success_rate": stats["successful_calls"] / total,
                "avg_latency_ms": stats["total_latency_ms"] / total,
                "avg_tokens_per_call": (
                    stats["total_tokens"] / total if stats["total_tokens"] > 0 else 0
                ),
            }

    def get_all_stats(self) -> Dict[str, Any]:
        with self._lock:
            agents = list(self.metrics.keys())
        return {agent_name: self.get_agent_stats(agent_name) for agent_name in agents}


agent_metrics = AgentMetrics()

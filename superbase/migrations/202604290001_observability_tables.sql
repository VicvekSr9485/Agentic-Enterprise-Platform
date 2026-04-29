-- ============================================================================
-- Observability + safety tables
--
-- Created as part of the Batch C hardening pass:
--   * hitl_approvals — durable HITL approval state across restarts/replicas.
--   * agent_metrics  — per-call agent telemetry, queryable across replicas.
--
-- Both tables are intentionally append-mostly. RLS is left to the caller's
-- service role key. Add row-level policies for multi-tenant deployments.
-- ============================================================================

CREATE TABLE IF NOT EXISTS hitl_approvals (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    draft_content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hitl_approvals_user_session_idx
    ON hitl_approvals (user_id, session_id);

CREATE INDEX IF NOT EXISTS hitl_approvals_created_at_idx
    ON hitl_approvals (created_at DESC);


CREATE TABLE IF NOT EXISTS agent_metrics (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    session_id TEXT,
    user_id TEXT,
    request_id TEXT,
    success BOOLEAN NOT NULL,
    latency_ms INTEGER,
    token_count INTEGER,
    error TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_metrics_agent_idx
    ON agent_metrics (agent_name, recorded_at DESC);

CREATE INDEX IF NOT EXISTS agent_metrics_recorded_at_idx
    ON agent_metrics (recorded_at DESC);

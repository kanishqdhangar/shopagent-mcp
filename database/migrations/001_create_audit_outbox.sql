CREATE TABLE IF NOT EXISTS audit_outbox (
    id UUID PRIMARY KEY,

    run_id UUID NOT NULL,
    node_name TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasoning TEXT,

    tokens_used INTEGER,
    latency_ms INTEGER,

    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,

    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    locked_at TIMESTAMPTZ,
    locked_by TEXT,

    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,

    CONSTRAINT audit_outbox_status_check
        CHECK (status IN ('pending', 'processing', 'delivered', 'dead')),

    CONSTRAINT audit_outbox_attempts_check
        CHECK (attempts >= 0 AND max_attempts > 0)
);

CREATE INDEX IF NOT EXISTS idx_audit_outbox_pending
ON audit_outbox (next_retry_at, created_at)
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_audit_outbox_processing
ON audit_outbox (locked_at)
WHERE status = 'processing';
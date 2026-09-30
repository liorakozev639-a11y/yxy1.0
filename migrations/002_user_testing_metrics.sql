CREATE TABLE IF NOT EXISTS test_users (
    id TEXT PRIMARY KEY,
    anonymous_id TEXT NOT NULL UNIQUE,
    cohort TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS test_events (
    id TEXT PRIMARY KEY,
    anonymous_id TEXT NOT NULL REFERENCES test_users(anonymous_id) ON DELETE CASCADE,
    session_id TEXT,
    plan_id TEXT,
    plan_item_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'session_created',
        'questionnaire_started',
        'questionnaire_completed',
        'recommendations_viewed',
        'task_started',
        'task_completed',
        'task_skipped',
        'task_replaced',
        'schedule_adjusted',
        'feedback_submitted',
        'flow_error'
    )),
    reason_code TEXT CHECK (reason_code IS NULL OR reason_code IN (
        'not_interested',
        'low_energy',
        'not_enough_time',
        'over_budget',
        'location_inconvenient',
        'too_difficult',
        'not_matching_current_state',
        'other'
    )),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idempotency_key TEXT NOT NULL,
    UNIQUE (idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_test_events_anonymous_time
ON test_events(anonymous_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_events_type_time
ON test_events(event_type, received_at DESC);

CREATE TABLE IF NOT EXISTS task_test_feedback (
    id TEXT PRIMARY KEY,
    anonymous_id TEXT NOT NULL REFERENCES test_users(anonymous_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    plan_item_id TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (plan_item_id)
);

CREATE INDEX IF NOT EXISTS idx_task_test_feedback_anonymous_time
ON task_test_feedback(anonymous_id, created_at DESC);

CREATE TABLE IF NOT EXISTS admin_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role = 'admin'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    id TEXT PRIMARY KEY,
    admin_user_id TEXT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_expiry
ON admin_sessions(expires_at);

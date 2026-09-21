CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    token_hash TEXT
);

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS stage TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::jsonb;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS token_hash TEXT;
ALTER TABLE sessions ALTER COLUMN token_hash DROP NOT NULL;

CREATE TABLE IF NOT EXISTS questionnaires (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('quick', 'deep')),
    question_ids JSONB NOT NULL,
    submitted BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS questionnaire_answers (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    value INTEGER CHECK (value BETWEEN 1 AND 4),
    skipped BOOLEAN NOT NULL DEFAULT FALSE,
    answered_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, question_id),
    CHECK (
        (skipped = TRUE AND value IS NULL)
        OR (skipped = FALSE AND value IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS profiles (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    profile_version INTEGER NOT NULL,
    scores JSONB NOT NULL,
    constraints JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    rule_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, profile_version)
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    density TEXT NOT NULL,
    free_start TIMESTAMPTZ NOT NULL,
    free_end TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL,
    parent_plan_id TEXT,
    unscheduled_task_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_id TEXT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    locked BOOLEAN NOT NULL DEFAULT FALSE,
    replacement_history JSONB NOT NULL DEFAULT '[]'::jsonb
);

ALTER TABLE plans ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE plan_items ADD COLUMN IF NOT EXISTS replacement_history JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS delivery_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel = 'web'),
    status TEXT NOT NULL CHECK (status IN ('ready', 'failed')),
    payload_json JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, plan_id, channel)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    linked_account_id TEXT
);

CREATE TABLE IF NOT EXISTS user_task_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    task_id TEXT,
    feedback_group TEXT NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL CHECK (
        action IN ('completed', 'skipped', 'replaced_from', 'replaced_to')
    ),
    duration_minutes INTEGER NOT NULL,
    outing TEXT,
    company TEXT,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_task_history_user_time
ON user_task_history(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_task_history_user_group
ON user_task_history(user_id, feedback_group);

CREATE TABLE IF NOT EXISTS execution_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_execution_events_item_time
ON execution_events(item_id, occurred_at);

CREATE TABLE IF NOT EXISTS task_feedback (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(plan_id, item_id)
);

CREATE TABLE IF NOT EXISTS session_task_exclusions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    feedback_group TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('low_rating', 'skipped')),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, feedback_group)
);

CREATE INDEX IF NOT EXISTS idx_session_task_exclusions_session
ON session_task_exclusions(session_id, created_at);

CREATE TABLE IF NOT EXISTS session_adjusted_task_exclusions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    adjustment TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_session_adjusted_task_exclusions_session
ON session_adjusted_task_exclusions(session_id, created_at);

CREATE TABLE IF NOT EXISTS quick_recommendation_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    available_minutes INTEGER NOT NULL CHECK (available_minutes BETWEEN 1 AND 480),
    energy_level TEXT NOT NULL CHECK (energy_level IN ('low', 'medium', 'high')),
    tasks_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quick_runs_session_time
ON quick_recommendation_runs(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS quick_recommendation_feedback (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES quick_recommendation_runs(id) ON DELETE CASCADE,
    task_id TEXT,
    action TEXT NOT NULL CHECK (action IN ('liked', 'disliked', 'rest_selected')),
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (
        (action = 'rest_selected' AND task_id IS NULL)
        OR (action IN ('liked', 'disliked') AND task_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_task_unique
ON quick_recommendation_feedback(run_id, task_id)
WHERE task_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_rest_unique
ON quick_recommendation_feedback(run_id)
WHERE action = 'rest_selected';

CREATE TABLE IF NOT EXISTS task_completion_reflections (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    sentiment TEXT NOT NULL CHECK (
        sentiment IN ('satisfied', 'neutral', 'dissatisfied')
    ),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (plan_id, item_id)
);

CREATE TABLE IF NOT EXISTS ai_generation_runs (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    generation_key TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'mock',
    context_json JSONB NOT NULL,
    brief_json JSONB NOT NULL,
    rejected_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (session_id, generation_key)
);

CREATE TABLE IF NOT EXISTS generated_tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    generation_key TEXT,
    ordinal INTEGER NOT NULL DEFAULT 0,
    semantic_signature TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, semantic_signature)
);

CREATE INDEX IF NOT EXISTS idx_generated_tasks_session
ON generated_tasks(session_id, created_at);

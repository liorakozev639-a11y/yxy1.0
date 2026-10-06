ALTER TABLE IF EXISTS test_events
DROP CONSTRAINT IF EXISTS test_events_idempotency_key_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_events_anonymous_idempotency
ON test_events(anonymous_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_test_users_last_seen
ON test_users(last_seen_at);

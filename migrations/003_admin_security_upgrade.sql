ALTER TABLE IF EXISTS admin_users
ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0);

ALTER TABLE IF EXISTS admin_users
ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_users_single_admin
ON admin_users(role) WHERE role = 'admin';

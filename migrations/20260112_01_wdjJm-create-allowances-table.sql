-- Create allowances table
-- depends: 20260111_01_gZHLU-create-initial-tables
CREATE TABLE allowances(
  user_id TEXT NOT NULL REFERENCES discord_users(user_id),
  created_at TEXT NOT NULL DEFAULT CURRENT_DATE,
  UNIQUE (user_id, created_at)
);

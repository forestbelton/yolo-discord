-- Create portfolio snapshots table
-- depends: 20260112_01_wdjJm-create-allowances-table
CREATE TABLE portfolio_snapshots(
  user_id TEXT NOT NULL REFERENCES discord_users(user_id),
  created_at TEXT NOT NULL DEFAULT CURRENT_DATE,
  data TEXT NOT NULL,
  UNIQUE (user_id, created_at)
);

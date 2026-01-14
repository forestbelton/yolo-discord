-- Create portfolio_snapshots index
-- depends: 20260112_02_Y01XZ-create-portfolio-snapshots-table
CREATE INDEX portfolio_snapshots_user_id_created_at_idx
  ON portfolio_snapshots (user_id, created_at);

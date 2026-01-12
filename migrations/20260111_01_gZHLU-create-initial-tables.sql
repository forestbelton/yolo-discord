-- Create initial tables
-- depends: 

CREATE TABLE discord_users(
  user_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id TEXT NOT NULL REFERENCES discord_users(user_id),
  type TEXT NOT NULL CHECK (type IN ('CREDIT', 'DEBIT')),
  amount_cents INTEGER NOT NULL,
  comment TEXT NOT NULL
);

CREATE INDEX transactions_user_id_idx
  ON transactions (user_id);

CREATE TABLE orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id TEXT NOT NULL REFERENCES discord_users(user_id),
  transaction_id INTEGER NOT NULL REFERENCES transactions(id),
  type TEXT NOT NULL CHECK (type in ('BUY', 'SELL')),
  security_name TEXT NOT NULL,
  security_price_cents INTEGER NOT NULL,
  quantity INTEGER NOT NULL
);

CREATE INDEX orders_user_id_transaction_id_idx
  ON orders (user_id, transaction_id);

CREATE TABLE security_prices(
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  price_cents INTEGER NOT NULL
);

CREATE INDEX security_prices_name_created_at_idx
  ON security_prices (name, created_at);


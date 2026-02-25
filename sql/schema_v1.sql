CREATE TABLE IF NOT EXISTS addresses (
  address TEXT PRIMARY KEY,
  first_seen_block BIGINT,
  last_seen_block BIGINT,
  tx_count BIGINT DEFAULT 0,
  contracts_deployed BIGINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
  tx_hash TEXT PRIMARY KEY,
  block_number BIGINT NOT NULL,
  from_address TEXT,
  to_address TEXT,
  value_wei NUMERIC,
  success BOOLEAN,
  timestamp TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS token_transfers (
  id BIGSERIAL PRIMARY KEY,
  tx_hash TEXT,
  token_address TEXT,
  from_address TEXT,
  to_address TEXT,
  amount NUMERIC,
  block_number BIGINT,
  timestamp TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS labels (
  id BIGSERIAL PRIMARY KEY,
  address TEXT NOT NULL,
  label TEXT NOT NULL,
  confidence NUMERIC NOT NULL,
  evidence JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS edges (
  id BIGSERIAL PRIMARY KEY,
  src_address TEXT NOT NULL,
  dst_address TEXT NOT NULL,
  tx_count BIGINT DEFAULT 0,
  total_value_wei NUMERIC DEFAULT 0,
  window_start TIMESTAMPTZ,
  window_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_state (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest_failures (
  id BIGSERIAL PRIMARY KEY,
  stage TEXT NOT NULL,
  start_block BIGINT,
  end_block BIGINT,
  error TEXT,
  retry_count INT DEFAULT 0,
  status TEXT DEFAULT 'open',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_thresholds (
  rule_type TEXT PRIMARY KEY,
  min_ratio NUMERIC,
  min_delta INT,
  min_count INT,
  cooldown_hours INT DEFAULT 6,
  enabled BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  type TEXT NOT NULL,
  address TEXT NOT NULL,
  severity TEXT NOT NULL,
  confidence NUMERIC NOT NULL,
  evidence JSONB,
  fingerprint TEXT,
  status TEXT DEFAULT 'new',
  assignee TEXT,
  ack_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingest_failures_status ON ingest_failures(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_number);
CREATE INDEX IF NOT EXISTS idx_transfer_block ON token_transfers(block_number);
CREATE INDEX IF NOT EXISTS idx_labels_address ON labels(address);
CREATE INDEX IF NOT EXISTS idx_edges_src_dst ON edges(src_address, dst_address);
CREATE UNIQUE INDEX IF NOT EXISTS ux_transfer_natural
  ON token_transfers(tx_hash, token_address, from_address, to_address, amount, block_number);
CREATE INDEX IF NOT EXISTS idx_alerts_address_created ON alerts(address, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type_created ON alerts(type, created_at DESC);

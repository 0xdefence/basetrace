CREATE TABLE IF NOT EXISTS alert_deliveries (
  id BIGSERIAL PRIMARY KEY,
  alert_id BIGINT REFERENCES alerts(id) ON DELETE SET NULL,
  channel TEXT NOT NULL,
  destination TEXT,
  status TEXT NOT NULL,
  attempts INT NOT NULL DEFAULT 1,
  error TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alert_deliveries_created ON alert_deliveries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_deliveries_status ON alert_deliveries(status, created_at DESC);

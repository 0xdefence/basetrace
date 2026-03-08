CREATE TABLE IF NOT EXISTS waitlist_signups (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  source TEXT DEFAULT 'alpha_page',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_waitlist_signups_created ON waitlist_signups(created_at DESC);

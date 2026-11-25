-- ZonaOK Push. Apply only to the private test D1 database.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  endpoint TEXT NOT NULL UNIQUE,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  preferences_json TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  last_test_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- The address is never stored. The key is a daily, one-way hash of the
-- Cloudflare supplied client IP; each address can create at most five devices
-- per UTC day. Old buckets can be removed after 8 days.
CREATE TABLE IF NOT EXISTS registration_limits (
  day_key TEXT NOT NULL,
  ip_hash TEXT NOT NULL,
  hits INTEGER NOT NULL DEFAULT 0 CHECK (hits BETWEEN 1 AND 5),
  PRIMARY KEY (day_key, ip_hash)
);

-- Reserved for the later, separately gated sports-notification system.
CREATE TABLE IF NOT EXISTS match_state (
  match_id TEXT PRIMARY KEY,
  observation_json TEXT NOT NULL,
  source_checked_at TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('start', 'goal', 'card', 'finish')),
  payload_json TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deliveries (
  event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'sending', 'sent', 'failed', 'expired')),
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until TEXT,
  next_attempt_at TEXT,
  sent_at TEXT,
  PRIMARY KEY (event_id, subscription_id)
);

CREATE INDEX IF NOT EXISTS deliveries_queue
  ON deliveries(state, next_attempt_at, lease_until);
CREATE INDEX IF NOT EXISTS registration_limits_expiry
  ON registration_limits(day_key);

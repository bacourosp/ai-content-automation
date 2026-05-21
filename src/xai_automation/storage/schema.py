SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  author_handle TEXT NOT NULL,
  created_at TEXT NOT NULL,
  text TEXT NOT NULL,
  url TEXT NOT NULL,
  lang TEXT NOT NULL DEFAULT '',
  text_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  state TEXT NOT NULL,
  topic_score INTEGER NOT NULL DEFAULT 0,
  score_json TEXT NOT NULL DEFAULT '',
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT '',
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_job_id ON assets(job_id);

CREATE TABLE IF NOT EXISTS publish_queue (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_queue_status ON publish_queue(status);
CREATE INDEX IF NOT EXISTS idx_publish_queue_job_id ON publish_queue(job_id);

CREATE TABLE IF NOT EXISTS cost_events (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  job_id TEXT NOT NULL DEFAULT '',
  asset_id TEXT NOT NULL DEFAULT '',
  month_key TEXT NOT NULL,
  cost_usd REAL NOT NULL,
  units INTEGER NOT NULL DEFAULT 1,
  details_json TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_events_month ON cost_events(provider, month_key);
CREATE INDEX IF NOT EXISTS idx_cost_events_job ON cost_events(job_id);

CREATE TABLE IF NOT EXISTS api_errors (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  job_id TEXT NOT NULL DEFAULT '',
  asset_id TEXT NOT NULL DEFAULT '',
  method TEXT NOT NULL,
  url TEXT NOT NULL,
  status_code INTEGER,
  message TEXT NOT NULL,
  request_json TEXT NOT NULL DEFAULT '',
  response_text TEXT NOT NULL DEFAULT '',
  is_quota INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_errors_created ON api_errors(created_at);
CREATE INDEX IF NOT EXISTS idx_api_errors_provider ON api_errors(provider);
CREATE INDEX IF NOT EXISTS idx_api_errors_job ON api_errors(job_id);

CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
"""

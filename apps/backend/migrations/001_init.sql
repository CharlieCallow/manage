-- CLAUDE.md §5 — full data model. Phase 0 only exercises a subset,
-- but the schema is the stable contract between front and back (§14).

CREATE TABLE IF NOT EXISTS personas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    prompt_template TEXT NOT NULL,
    model           TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    prompt_template TEXT NOT NULL,
    model           TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    inputs_json  TEXT NOT NULL,
    status       TEXT NOT NULL,
    cost_usd     REAL NOT NULL DEFAULT 0,
    budget_usd   REAL NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS job_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id   TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    seq      INTEGER NOT NULL,
    payload  TEXT NOT NULL,
    ts       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id, seq);

CREATE TABLE IF NOT EXISTS artifacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    content_md   TEXT,
    content_json TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_calls (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    model          TEXT NOT NULL,
    input_tokens   INTEGER NOT NULL,
    output_tokens  INTEGER NOT NULL,
    cost_usd       REAL NOT NULL,
    ts             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL UNIQUE,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL DEFAULT (datetime('now')),
    snapshot_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS persona_performance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id  INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    period      TEXT NOT NULL,
    trades      INTEGER NOT NULL DEFAULT 0,
    hit_rate    REAL,
    avg_return  REAL,
    UNIQUE (persona_id, period)
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content_md  TEXT NOT NULL,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed analysts (CLAUDE.md §5: valuation, sentiment, fundamentals, technicals, risk, pm)
INSERT OR IGNORE INTO analysts (name, prompt_template, model) VALUES
    ('valuation',    'Placeholder — Phase 1',        'claude-sonnet-4-6'),
    ('sentiment',    'Placeholder — Phase 1',        'claude-haiku-4-5'),
    ('fundamentals', 'Placeholder — Phase 1',        'claude-sonnet-4-6'),
    ('technicals',   'Placeholder — Phase 1',        'claude-sonnet-4-6'),
    ('risk',         'Placeholder — Phase 1',        'claude-sonnet-4-6'),
    ('pm',           'Placeholder — Phase 1',        'claude-opus-4-7');

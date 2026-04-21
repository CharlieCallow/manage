-- Idea candidates surfaced by the ideation flow.
-- Each row is one persona's suggestion of a ticker worth a deeper look;
-- status flips from pending → approved (spawns a research job) or
-- dismissed (no side effect).

CREATE TABLE IF NOT EXISTS ideas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ideation_job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    persona         TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    thesis          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    research_job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_job ON ideas(ideation_job_id);

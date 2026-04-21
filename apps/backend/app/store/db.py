"""SQLite access layer. CLAUDE.md §4 — SQLAlchemy Core, no ORM.

Migrations run at startup (§4). The schema is the stable contract (§14);
don't rename fields without a new migration file.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text

from app.config import REPO_ROOT, settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_file = settings.database_file
        db_file.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_file}",
            future=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(_engine, "connect")
        def _on_connect(dbapi_conn: sqlite3.Connection, _rec: object) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys = ON")
            dbapi_conn.execute("PRAGMA journal_mode = WAL")
    return _engine


def migrations_dir() -> Path:
    return REPO_ROOT / "apps" / "backend" / "migrations"


def run_migrations() -> None:
    """Apply every *.sql file in migrations/ in filename order, idempotently."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS _migrations ("
                "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
            )
        )
        applied = {
            row[0]
            for row in conn.execute(text("SELECT name FROM _migrations")).fetchall()
        }

    for path in sorted(migrations_dir().glob("*.sql")):
        if path.name in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        logger.info("Applying migration %s", path.name)
        with engine.begin() as conn:
            for stmt in _split_sql(sql):
                if stmt.strip():
                    conn.exec_driver_sql(stmt)
            conn.execute(
                text("INSERT INTO _migrations (name) VALUES (:n)"), {"n": path.name}
            )


def _split_sql(sql: str) -> list[str]:
    # Naive splitter — fine for our hand-written migrations which have no
    # semicolons inside string literals or triggers.
    return [s for s in sql.split(";") if s.strip()]


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Raw sqlite3 connection for ad-hoc queries. Autocommits on exit.

    Bypasses the SQLAlchemy pool so `row_factory` applies cleanly — the pool
    hands back a proxy wrapper whose attribute writes don't forward.
    """
    get_engine()  # ensure migrations path / settings are resolved
    conn = sqlite3.connect(settings.database_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_persona(name: str, prompt_template: str, model: str) -> int:
    """Upsert and return persona id."""
    with connection() as conn:
        cur = conn.execute("SELECT id FROM personas WHERE name = ?", (name,))
        row = cur.fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO personas (name, prompt_template, model, config_json) "
                "VALUES (?, ?, ?, ?)",
                (name, prompt_template, model, json.dumps({})),
            )
            return int(cur.lastrowid or 0)
        conn.execute(
            "UPDATE personas SET prompt_template = ? WHERE id = ?",
            (prompt_template, row["id"]),
        )
        return int(row["id"])


def get_persona_by_name(name: str) -> sqlite3.Row | None:
    with connection() as conn:
        cur = conn.execute("SELECT * FROM personas WHERE name = ?", (name,))
        row: sqlite3.Row | None = cur.fetchone()
        return row

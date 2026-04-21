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
from typing import Any

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


def _upsert(
    table: str, name: str, prompt_template: str, model: str
) -> int:
    # Only called with hard-coded table names; not user input.
    if table not in {"personas", "analysts"}:
        raise ValueError(f"invalid table for upsert: {table}")
    with connection() as conn:
        cur = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))  # noqa: S608
        row = cur.fetchone()
        if row is None:
            cur = conn.execute(
                f"INSERT INTO {table} (name, prompt_template, model, config_json) "  # noqa: S608
                "VALUES (?, ?, ?, ?)",
                (name, prompt_template, model, json.dumps({})),
            )
            return int(cur.lastrowid or 0)
        conn.execute(
            f"UPDATE {table} SET prompt_template = ? WHERE id = ?",  # noqa: S608
            (prompt_template, row["id"]),
        )
        return int(row["id"])


def upsert_persona(name: str, prompt_template: str, model: str) -> int:
    return _upsert("personas", name, prompt_template, model)


def upsert_analyst(name: str, prompt_template: str, model: str) -> int:
    return _upsert("analysts", name, prompt_template, model)


def get_persona_by_name(name: str) -> sqlite3.Row | None:
    with connection() as conn:
        cur = conn.execute("SELECT * FROM personas WHERE name = ?", (name,))
        row: sqlite3.Row | None = cur.fetchone()
        return row


def get_analyst_by_name(name: str) -> sqlite3.Row | None:
    with connection() as conn:
        cur = conn.execute("SELECT * FROM analysts WHERE name = ?", (name,))
        row: sqlite3.Row | None = cur.fetchone()
        return row


def insert_artifact(
    job_id: str,
    kind: str,
    content_md: str | None = None,
    content_json: str | None = None,
) -> int:
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO artifacts (job_id, kind, content_md, content_json) "
            "VALUES (?, ?, ?, ?)",
            (job_id, kind, content_md, content_json),
        )
        return int(cur.lastrowid or 0)


def list_artifacts_for_job(job_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        cur = conn.execute(
            "SELECT id, job_id, kind, content_md, content_json, created_at "
            "FROM artifacts WHERE job_id = ? ORDER BY id",
            (job_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_roster(table: str) -> list[dict[str, Any]]:
    if table not in {"personas", "analysts"}:
        raise ValueError(f"invalid roster table: {table}")
    with connection() as conn:
        cur = conn.execute(
            f"SELECT id, name, prompt_template, model, enabled, created_at "  # noqa: S608
            f"FROM {table} ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]


def get_roster_row(table: str, name: str) -> dict[str, Any] | None:
    if table not in {"personas", "analysts"}:
        raise ValueError(f"invalid roster table: {table}")
    with connection() as conn:
        cur = conn.execute(
            f"SELECT id, name, prompt_template, model, enabled, created_at "  # noqa: S608
            f"FROM {table} WHERE name = ?",
            (name,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


_ROSTER_UPDATABLE: frozenset[str] = frozenset({"prompt_template", "model", "enabled"})


def update_roster_row(table: str, name: str, fields: dict[str, Any]) -> bool:
    if table not in {"personas", "analysts"}:
        raise ValueError(f"invalid roster table: {table}")
    bad = set(fields) - _ROSTER_UPDATABLE
    if bad:
        raise ValueError(f"refusing to update unknown roster columns: {sorted(bad)}")
    if not fields:
        return True
    cols = ", ".join(f"{k} = ?" for k in fields)
    sql = f"UPDATE {table} SET {cols} WHERE name = ?"  # noqa: S608
    with connection() as conn:
        cur = conn.execute(sql, (*fields.values(), name))
        return cur.rowcount > 0


def list_performance_for_persona(persona_id: int) -> list[dict[str, Any]]:
    with connection() as conn:
        cur = conn.execute(
            "SELECT id, persona_id, period, trades, hit_rate, avg_return "
            "FROM persona_performance WHERE persona_id = ? ORDER BY period",
            (persona_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_recent_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        cur = conn.execute(
            "SELECT id, type, status, cost_usd, budget_usd, started_at, "
            "finished_at, error, inputs_json FROM jobs "
            "ORDER BY COALESCE(started_at, id) DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]

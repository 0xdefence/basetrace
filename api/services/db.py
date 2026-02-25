import os
from contextlib import contextmanager

import psycopg2


def get_dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/basetrace")


@contextmanager
def get_conn():
    conn = psycopg2.connect(get_dsn())
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_schema_version() -> str | None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("SELECT version FROM schema_migrations ORDER BY applied_at DESC, version DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None


def assert_expected_schema_version() -> None:
    expected = os.getenv("SCHEMA_VERSION")
    if not expected:
        return
    current = get_schema_version()
    if current != expected:
        raise RuntimeError(f"schema version mismatch: expected={expected} current={current}")

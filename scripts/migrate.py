#!/usr/bin/env python3
import os
from pathlib import Path

import psycopg2


def dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/basetrace")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    migrations_dir = root / "sql" / "migrations"
    files = sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())

    conn = psycopg2.connect(dsn())
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        cur.execute("SELECT version FROM schema_migrations")
        applied = {r[0] for r in cur.fetchall()}

        for f in files:
            if f.name in applied:
                continue
            sql = f.read_text(encoding="utf-8")
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations(version) VALUES(%s)", (f.name,))
            conn.commit()
            print(f"applied {f.name}")

        print("migrations complete")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

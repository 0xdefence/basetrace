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

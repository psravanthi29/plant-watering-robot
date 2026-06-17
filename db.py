"""Database access layer — Postgres (Supabase) in the cloud, SQLite locally/tests.

If DATABASE_URL is set (e.g. on Render pointing at Supabase) the app uses
Postgres; otherwise it uses a local SQLite file. Tests pass ":memory:" to force
SQLite regardless.

Call sites keep using sqlite-style `?` placeholders and rows that support BOTH
`row[0]` and `row["col"]` (and `dict(row)`); this module translates `?` -> `%s`
and provides hybrid rows for Postgres so the rest of the code is dialect-agnostic.
"""

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

DEFAULT_SQLITE_PATH = "plant.db"


def _is_pg(path):
    """Whether a connection for `path` will be Postgres (mirrors connect())."""
    return USE_PG and path != ":memory:"


def auto_pk(path=DEFAULT_SQLITE_PATH):
    """Auto-increment primary-key column def for the dialect `path` resolves to.

    Must be per-path, not global: tests force SQLite via ':memory:' even when
    DATABASE_URL is set, so the PK type has to match the real target.
    """
    return "BIGSERIAL PRIMARY KEY" if _is_pg(path) else "INTEGER PRIMARY KEY AUTOINCREMENT"


if USE_PG:
    import psycopg

    # A process-wide pool keeps connections warm. Without it, every request paid a
    # fresh Postgres connection handshake to Supabase (~2s, TLS+auth, cross-region),
    # which made every data-loading click slow. max_size matches gunicorn --threads.
    # check= validates a connection before handing it out, so a connection Supabase
    # closed while idle is transparently replaced instead of erroring a request.
    # psycopg_pool is imported lazily here so db.py still imports in SQLite/test
    # contexts (and CI) where the pool dependency isn't installed.
    _pool = None

    def _get_pool():
        global _pool
        if _pool is None:
            from psycopg_pool import ConnectionPool
            _pool = ConnectionPool(
                DATABASE_URL,
                min_size=1,
                max_size=8,
                max_idle=120,
                check=ConnectionPool.check_connection,
                open=True,
            )
        return _pool

    class _HybridRow:
        """Supports row[0], row['col'] and dict(row) — matches sqlite3.Row."""
        __slots__ = ("_names", "_values", "_map")

        def __init__(self, names, values):
            self._names = names
            self._values = tuple(values)
            self._map = dict(zip(names, self._values))

        def __getitem__(self, key):
            return self._values[key] if isinstance(key, int) else self._map[key]

        def __iter__(self):
            return iter(self._values)

        def __len__(self):
            return len(self._values)

        def keys(self):
            return list(self._names)

        def get(self, key, default=None):
            return self._map.get(key, default)

    def _hybrid_rows(cursor):
        names = [c.name for c in cursor.description] if cursor.description else []
        return lambda values: _HybridRow(names, values)

    class _PgConnection:
        """Adapter exposing the slice of the sqlite3 Connection API our code uses.

        Wraps a connection borrowed from the pool; close() returns it to the pool
        (rolling back any uncommitted state first) rather than tearing it down.
        """

        def __init__(self, raw, pool):
            self._raw = raw
            self._pool = pool
            self.row_factory = None  # accepted for sqlite-compat, ignored

        def execute(self, sql, params=()):
            cur = self._raw.cursor(row_factory=_hybrid_rows)
            cur.execute(sql.replace("?", "%s"), params)
            return cur

        def cursor(self):
            return self._raw.cursor(row_factory=_hybrid_rows)

        def commit(self):
            self._raw.commit()

        def close(self):
            if self._raw is None:
                return
            try:
                self._raw.rollback()  # discard anything uncommitted before reuse
            except Exception:
                pass
            try:
                self._pool.putconn(self._raw)
            except Exception:
                # If returning fails, close it so the pool can open a fresh one.
                try:
                    self._raw.close()
                except Exception:
                    pass
            self._raw = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                self._raw.commit() if exc_type is None else self._raw.rollback()
            finally:
                self.close()
            return False


def connect(path=DEFAULT_SQLITE_PATH):
    """SQLite when path is ':memory:' or DATABASE_URL is unset; Postgres otherwise."""
    if path == ":memory:" or not USE_PG:
        conn = sqlite3.connect(path or DEFAULT_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    pool = _get_pool()
    return _PgConnection(pool.getconn(), pool)


def insert_or_ignore(table, columns, conflict_columns):
    """'Insert, skip on conflict' statement (uses ? placeholders).

    The `ON CONFLICT (...) DO NOTHING` form is valid in both SQLite (3.24+) and
    Postgres, so this is dialect-agnostic.
    """
    cols = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    conflict = ", ".join(conflict_columns)
    return (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO NOTHING")

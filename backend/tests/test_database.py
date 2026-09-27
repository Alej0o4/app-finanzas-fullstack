"""Test de `app/core/database.engine_kwargs_for_url` (Fase 31, T7 — parte SQLite, sin
marker `postgres`: es una función pura, no necesita una conexión real para probarse).

La parte Postgres de T7 (sesión realmente en UTC pese a un `ALTER DATABASE ... SET
timezone`) vive en `tests/test_concurrency_pg.py`, marcada `postgres`.
"""

from app.core.database import engine_kwargs_for_url


class TestEngineKwargsForUrl:
    def test_sqlite_url_gets_check_same_thread_false(self):
        kwargs = engine_kwargs_for_url("sqlite:///./finanzas.db")
        assert kwargs == {"connect_args": {"check_same_thread": False}}

    def test_sqlite_memory_url_gets_check_same_thread_false(self):
        kwargs = engine_kwargs_for_url("sqlite://")
        assert kwargs == {"connect_args": {"check_same_thread": False}}

    def test_postgresql_url_gets_utc_timezone_option(self):
        kwargs = engine_kwargs_for_url("postgresql://user:pass@localhost:5432/oikos_test")
        assert kwargs == {"connect_args": {"options": "-c timezone=UTC"}}

    def test_postgresql_url_does_not_get_check_same_thread(self):
        """`check_same_thread` es un `connect_args` específico del driver de SQLite —
        pasarlo a psycopg reventaría la conexión con un TypeError."""
        kwargs = engine_kwargs_for_url("postgresql://user:pass@localhost:5432/oikos_test")
        assert "check_same_thread" not in kwargs.get("connect_args", {})

    def test_unknown_dialect_gets_no_extra_kwargs(self):
        assert engine_kwargs_for_url("mysql://user:pass@localhost/db") == {}

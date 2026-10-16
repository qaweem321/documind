from importlib import resources
from typing import Any

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Any fixed number: every app instance takes the same lock, so only one runs migrations at a time.
MIGRATION_LOCK = 72_116_401


async def _configure(conn: AsyncConnection[dict[str, Any]]) -> None:
    await register_vector_async(conn)


async def run_migrations(url: str) -> list[str]:
    """Applies migrations/*.sql in order, once each, inside a transaction per file."""
    applied: list[str] = []
    async with await AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
            )
            done = {
                row[0] for row in await (await conn.execute("SELECT name FROM schema_migrations")).fetchall()
            }
            files = sorted(
                (f for f in resources.files("app.migrations").iterdir() if f.name.endswith(".sql")),
                key=lambda f: f.name,
            )
            for file in files:
                if file.name in done:
                    continue
                async with conn.transaction():
                    await conn.execute(file.read_text())
                    await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (file.name,))
                applied.append(file.name)
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
    return applied


def create_pool(url: str) -> AsyncConnectionPool[AsyncConnection[dict[str, Any]]]:
    return AsyncConnectionPool(
        url,
        min_size=1,
        max_size=10,
        open=False,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        connection_class=AsyncConnection[dict[str, Any]],
    )

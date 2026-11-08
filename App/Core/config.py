import os
from contextlib import contextmanager
from functools import lru_cache

from dotenv import load_dotenv
from neo4j import GraphDatabase
from psycopg2 import pool

load_dotenv()


def _require(name: str) -> str:
    """Fail fast with a clear message if a required env var is missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name} (check your .env file)")
    return value


# --- PostgreSQL / pgvector ---
PG_USER = _require("PG_USER")
PG_PASS = _require("PG_PASS")
PG_DB = _require("PG_DATABASE")
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")

# --- Neo4j ---
NEO4J_USER = _require("NEO4J_USER")
NEO4J_PASS = _require("NEO4J_PASS")
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")


@lru_cache(maxsize=1)
def get_postgres_pool() -> pool.ThreadedConnectionPool:
    """Created once on first use, then reused for the life of the process."""
    return pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        host=PG_HOST,
        port=PG_PORT,
    )


@contextmanager
def postgres_cursor():
    """
    Borrow a pooled connection and yield a cursor.
    Commits on success, rolls back on error, and always returns the
    connection to the pool.

    Usage:
        with postgres_cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    """
    pg_pool = get_postgres_pool()
    conn = pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pg_pool.putconn(conn)


@lru_cache(maxsize=1)
def get_neo4j_driver():
    """Long-lived singleton. The driver manages its own connection pool."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def close_connections() -> None:
    """Call once at application shutdown (e.g. FastAPI lifespan, or end of main.py)."""
    if get_postgres_pool.cache_info().currsize:
        get_postgres_pool().closeall()
        get_postgres_pool.cache_clear()
    if get_neo4j_driver.cache_info().currsize:
        get_neo4j_driver().close()
        get_neo4j_driver.cache_clear()
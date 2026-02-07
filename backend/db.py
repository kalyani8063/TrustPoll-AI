import os
from psycopg2 import pool as pg_pool

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

MIN_CONN = int(os.getenv("DB_POOL_MIN", "1"))
MAX_CONN = int(os.getenv("DB_POOL_MAX", "10"))

_POOL = pg_pool.SimpleConnectionPool(
    MIN_CONN,
    MAX_CONN,
    dsn=DATABASE_URL,
    sslmode="require",
    connect_timeout=10
)

def get_connection():
    return _POOL.getconn()

def release_connection(conn):
    if conn:
        _POOL.putconn(conn)

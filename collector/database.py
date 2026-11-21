import os
import time
import psycopg2
from psycopg2 import OperationalError, InterfaceError

# -----------------------------------------------------------------------------
# Database Configuration from Environment Variables
# -----------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "health_monitor")
DB_USER = os.getenv("DB_USER", "monitor_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "change_this_to_a_secure_password")
DB_PORT = os.getenv("DB_PORT", "5432")


def connect_with_retry(max_retries=None, initial_delay=3, is_running=None):
    """
    Establish a connection to the PostgreSQL database with retry logic.
    Handles startup delays when PostgreSQL is initializing.

    :param max_retries: Maximum number of connection attempts (None for infinite)
    :param initial_delay: Initial retry backoff delay in seconds
    :param is_running: Optional callable returning bool to check for shutdown signals
    """
    delay = initial_delay
    attempt = 1

    def should_continue():
        return is_running() if callable(is_running) else True

    while should_continue() and (max_retries is None or attempt <= max_retries):
        try:
            print(f"[INFO] Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME} (attempt {attempt})...")
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
                connect_timeout=10,
            )
            # Enable autocommit or commit explicitly per transaction
            conn.autocommit = True
            print("[INFO] Successfully connected to PostgreSQL.")
            return conn
        except (OperationalError, Exception) as err:
            print(f"[WARN] Connection failed: {err}")
            print(f"[INFO] Retrying in {delay} seconds...")
            time.sleep(delay)
            # Exponential backoff capped at 30 seconds
            delay = min(delay * 1.5, 30)
            attempt += 1

    if callable(is_running) and not is_running():
        print("[INFO] Shutdown requested during connection attempts.")
        return None

    raise ConnectionError(f"Could not connect to database after {max_retries} attempts.")


def init_database(conn):
    """
    Ensures that the 'system_metrics' table and indexes exist.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS system_metrics (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL,
        cpu_percent FLOAT NOT NULL,
        memory_percent FLOAT NOT NULL,
        disk_percent FLOAT NOT NULL,
        uptime FLOAT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
    """
    with conn.cursor() as cursor:
        cursor.execute(create_table_sql)
    print("[INFO] Verified 'system_metrics' table and index.")


def insert_metrics(conn, metrics):
    """
    Inserts a metrics reading into the 'system_metrics' table using
    parameterized SQL to protect against injection and formatting bugs.
    """
    insert_sql = """
    INSERT INTO system_metrics (timestamp, cpu_percent, memory_percent, disk_percent, uptime)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id;
    """
    with conn.cursor() as cursor:
        cursor.execute(
            insert_sql,
            (
                metrics["timestamp"],
                metrics["cpu_percent"],
                metrics["memory_percent"],
                metrics["disk_percent"],
                metrics["uptime"],
            ),
        )
        record_id = cursor.fetchone()[0]
        return record_id

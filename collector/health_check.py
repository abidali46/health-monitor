import os
import sys
import time
import signal
from datetime import datetime, timezone
import psutil

from database import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    connect_with_retry,
    init_database,
    insert_metrics,
    OperationalError,
    InterfaceError,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
# Collection interval in seconds (default: 30)
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "30"))

# Flag to support graceful shutdown on SIGINT / SIGTERM
running = True


def handle_shutdown_signal(signum, frame):
    """Handle graceful shutdown signals from Docker or terminal."""
    global running
    sig_name = signal.Signals(signum).name
    print(f"\n[INFO] Received signal {sig_name}. Initiating graceful shutdown...")
    running = False


# Register signal handlers for clean container termination
signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)


def collect_metrics():
    """
    Collects system metrics using psutil:
    - cpu_percent: Float over 1 second sample window
    - memory_percent: Float virtual memory utilization
    - disk_percent: Float root filesystem disk usage
    - uptime: Float total system uptime in seconds
    """
    # Sample CPU over a 1-second interval
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Virtual memory percentage
    memory_info = psutil.virtual_memory()
    memory_percent = float(memory_info.percent)
    
    # Root filesystem disk percentage
    disk_info = psutil.disk_usage("/")
    disk_percent = float(disk_info.percent)
    
    # System uptime in seconds
    boot_time = psutil.boot_time()
    uptime = float(time.time() - boot_time)

    # Current UTC timestamp with timezone
    timestamp = datetime.now(timezone.utc)

    return {
        "timestamp": timestamp,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "disk_percent": disk_percent,
        "uptime": round(uptime, 2),
    }


def main():
    """Main execution loop of the health collector service."""
    global running
    print("=" * 60)
    print("   Starting System Health Monitor - Metrics Collector")
    print("=" * 60)
    print(f"[CONFIG] Target DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"[CONFIG] Collection Interval: {COLLECTION_INTERVAL} seconds\n")

    conn = None
    try:
        # Step 1: Initial connection with retry logic
        conn = connect_with_retry(is_running=lambda: running)
        if not conn:
            sys.exit(0)

        # Step 2: Ensure database schema is ready
        init_database(conn)

        # Step 3: Main metrics collection loop
        print(f"[INFO] Entering metric collection loop (every {COLLECTION_INTERVAL}s)...\n")
        while running:
            loop_start = time.time()

            try:
                # Collect metrics using psutil (takes ~1s for CPU measurement)
                metrics = collect_metrics()

                # Insert into PostgreSQL using parameterized query
                record_id = insert_metrics(conn, metrics)

                # Format human-readable output to console
                ts_str = metrics["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
                print(
                    f"[{ts_str}] [ID:{record_id:04d}] "
                    f"CPU: {metrics['cpu_percent']:5.1f}% | "
                    f"RAM: {metrics['memory_percent']:5.1f}% | "
                    f"Disk: {metrics['disk_percent']:5.1f}% | "
                    f"Uptime: {metrics['uptime']:,.1f}s"
                )

            except (OperationalError, InterfaceError) as db_err:
                # Handle dropped or interrupted database connections
                print(f"[WARN] Database connection lost: {db_err}")
                print("[INFO] Attempting to reconnect...")
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                conn = connect_with_retry(max_retries=None, initial_delay=3, is_running=lambda: running)
                if not running or not conn:
                    break
                init_database(conn)
                print("[INFO] Reconnection successful. Resuming collection.")

            except Exception as ex:
                print(f"[ERROR] Unexpected error during collection: {ex}")

            # Calculate remaining sleep time to maintain precise collection intervals
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, COLLECTION_INTERVAL - elapsed)

            # Sleep in 1-second increments so shutdown signals are responsive
            sleep_steps = int(sleep_time)
            for _ in range(sleep_steps):
                if not running:
                    break
                time.sleep(1)
            if running and (sleep_time - sleep_steps) > 0:
                time.sleep(sleep_time - sleep_steps)

    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received.")
    finally:
        # Step 4: Clean resource cleanup
        if conn:
            try:
                conn.close()
                print("[INFO] PostgreSQL connection closed.")
            except Exception as close_err:
                print(f"[WARN] Error closing connection: {close_err}")
        print("[INFO] System Health Monitor stopped gracefully.")


if __name__ == "__main__":
    main()

import json, logging, os, time
from datetime import datetime, timezone
from pathlib import Path
import pymysql
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
LOGS = BASE / "logs"
LOGS.mkdir(exist_ok=True)
logging.basicConfig(filename=LOGS / "failover.log", level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")

def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")

def event(name, details):
    record = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "event": name, "details": details}
    with (LOGS / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    logging.info("%s | %s", name, details)

def check_replica():
    conn = pymysql.connect(
        host=os.getenv("REPLICA_HOST", "127.0.0.1"),
        port=int(os.getenv("REPLICA_PORT", "3306")),
        user=os.environ["MONITOR_USER"],
        password=os.environ["MONITOR_PASSWORD"],
        connect_timeout=5, read_timeout=10, autocommit=True,
        cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("SHOW REPLICA STATUS")
            except pymysql.MySQLError:
                cur.execute("SHOW SLAVE STATUS")
            status = cur.fetchone()
            if not status:
                raise RuntimeError("No replica status returned; verify this is a replica.")
            io = status.get("Replica_IO_Running", status.get("Slave_IO_Running"))
            sql = status.get("Replica_SQL_Running", status.get("Slave_SQL_Running"))
            lag = status.get("Seconds_Behind_Source", status.get("Seconds_Behind_Master"))
            limit = int(os.getenv("MAX_LAG_SECONDS", "30"))
            if io != "Yes" or sql != "Yes" or lag is None:
                event("UNHEALTHY_OR_UNKNOWN", {"io": io, "sql": sql, "lag": lag})
                return
            lag = int(lag)
            if lag > limit:
                event("DRY_RUN_ALERT" if flag("DRY_RUN", True) else "FAILOVER_CANDIDATE",
                      {"lag_seconds": lag, "threshold": limit})
                if not flag("DRY_RUN", True):
                    promote_safely()
            else:
                event("REPLICA_OK", {"lag_seconds": lag, "threshold": limit})
    finally:
        conn.close()

def promote_safely():
    # Intentionally no automatic promotion SQL: requires topology-specific validation.
    if not flag("ENABLE_PROMOTION") or not flag("OLD_PRIMARY_FENCED") or not flag("PROMOTION_APPROVED"):
        event("PROMOTION_BLOCKED", "Require ENABLE_PROMOTION, OLD_PRIMARY_FENCED, and PROMOTION_APPROVED.")
        return
    event("PROMOTION_REQUIRES_RUNBOOK",
          "Safety flags passed. Run the tested topology-specific promotion procedure; no SQL was executed.")

def main():
    event("MONITOR_STARTED", {"dry_run": flag("DRY_RUN", True)})
    while True:
        try:
            check_replica()
        except Exception as exc:
            event("MONITOR_ERROR", repr(exc))
        time.sleep(max(5, int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))))

if __name__ == "__main__":
    main()

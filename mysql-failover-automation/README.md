# MySQL Replica Lag Monitor and Failover Safety Demo

Python project based on the task: monitor replica lag, compare it with a threshold, log failover candidates, and provide guarded failover workflow.

## Safety
This is a monitoring starter, not a production failover controller. High replica lag does not prove the primary is down. Production failover requires independent primary health checks, fencing the old primary, GTID/binlog consistency checks, and a tested recovery plan. This script intentionally does not run `CHANGE MASTER TO`, `CHANGE REPLICATION SOURCE TO`, or `STOP REPLICA` automatically.

## Setup (Windows)
1. Install Python 3.10+ and have access to a MySQL replica.
2. Open Command Prompt in this folder:
   ```bat
   python -m venv .venv
   .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and enter your replica host and dedicated monitoring account credentials.
4. Keep `DRY_RUN=true` and all promotion flags false while testing.
5. Run:
   ```bat
   python main.py
   ```
6. Stop with Ctrl+C. Check `logs/failover.log` and `logs/events.jsonl`.

## Workflow
1. Connect to the replica using PyMySQL.
2. Query `SHOW REPLICA STATUS` (falls back to `SHOW SLAVE STATUS` for older versions).
3. Check replication IO/SQL thread health and `Seconds_Behind_Source` / `Seconds_Behind_Master`.
4. Compare lag with `MAX_LAG_SECONDS`.
5. Log a dry-run alert or failover candidate.
6. Require explicit safety gates before even directing an operator to a topology-specific promotion runbook.

## Configuration
- `REPLICA_HOST`, `REPLICA_PORT`: replica connection.
- `MONITOR_USER`, `MONITOR_PASSWORD`: least-privilege monitoring credentials.
- `MAX_LAG_SECONDS`: lag threshold (default 30).
- `CHECK_INTERVAL_SECONDS`: polling interval (default 30).
- `DRY_RUN`: defaults to true.
- `ENABLE_PROMOTION`, `OLD_PRIMARY_FENCED`, `PROMOTION_APPROVED`: default false safety gates.

## Windows Task Scheduler
For continuous monitoring, prefer a service manager. If using Task Scheduler, configure a repeating trigger and set “If the task is already running” to “Do not start a new instance”. Program: full path to `.venv\\Scripts\\python.exe`; arguments: `main.py`; Start in: this project folder.

## Notes
`Seconds_Behind_Source` can be NULL; the script treats unknown lag as unsafe. Status fields vary across MySQL versions. Use a dedicated monitoring account, never commit `.env`, and consider MySQL InnoDB Cluster / MySQL Router or a proven failover manager for production.

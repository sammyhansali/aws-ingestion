"""
Stress experiments targeting DMS edge cases.
Run manually, one scenario at a time.

Scenarios:
  --scenario burst        50+ rapid UPDATEs to same row within 1 second
  --scenario concurrent   Multiple connections updating same row simultaneously
  --scenario ghost        INSERT immediately followed by DELETE before DMS flush
  --scenario large-txn    Single transaction touching 5000 rows
  --scenario rollback     Write changes then roll back; DMS must NOT surface these

Env vars required:
    RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
"""

import argparse
import os
import threading
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("RDS_HOST"),
    "port": os.environ.get("RDS_PORT"),
    "dbname": os.environ.get("RDS_DBNAME"),
    "user": os.environ.get("RDS_USER"),
    "password": os.environ.get("RDS_PASSWORD"),
}

N_BURST = 50
N_LARGE_TXN = 5000
N_CONCURRENT_THREADS = 10


def make_con():
    return psycopg2.connect(**DB_CONFIG)


def log(scenario: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{scenario}] {msg}")


def scenario_burst(con) -> None:
    """
    N_BURST rapid UPDATEs to the same row within one second.
    Expect DMS to capture all N_BURST events (at-least-once).
    Reconstruction should reflect only the final state.
    """
    # 1. pick or insert a target row, note its id
    # 2. in a tight loop, UPDATE the row N_BURST times (e.g. increment user_id each time)
    # 3. commit after all updates
    # 4. log triggered_at and id
    pass


def scenario_concurrent(con) -> None:
    """
    N_CONCURRENT_THREADS connections each update the same row simultaneously.
    Expect DMS to capture all updates; reconstruction should reflect the last committed state.
    """
    # 1. pick or insert a target row, note its id
    # 2. spawn N_CONCURRENT_THREADS threads, each opening its own connection
    # 3. each thread UPDATEs the same row with a different user_id and commits
    # 4. join all threads
    # 5. log triggered_at and id
    pass


def scenario_ghost(con) -> None:
    """
    INSERT a row then immediately DELETE it in separate transactions before DMS flushes.
    Expect: DMS may capture both I+D, or coalesce to nothing.
    Reconstruction must not leave the row in current-state.
    """
    # 1. INSERT a new row, commit — note the id
    # 2. immediately DELETE that id, commit
    # 3. log triggered_at and id
    pass


def scenario_large_txn(con) -> None:
    """
    Single transaction touching N_LARGE_TXN rows.
    Expect DMS to capture all rows in one batch; tests memory/buffer behavior.
    """
    # 1. open a transaction
    # 2. UPDATE N_LARGE_TXN random rows (order by random() limit N)
    # 3. commit in one shot
    # 4. log triggered_at and row count
    pass


def scenario_rollback(con) -> None:
    """
    Begin a transaction, UPDATE several rows, then roll back.
    DMS must NOT surface any of these changes.
    """
    # 1. open a transaction
    # 2. UPDATE several rows
    # 3. roll back
    # 4. log triggered_at — after the run, verify no events appear in change-log
    pass


SCENARIOS = {
    "burst": scenario_burst,
    "concurrent": scenario_concurrent,
    "ghost": scenario_ghost,
    "large-txn": scenario_large_txn,
    "rollback": scenario_rollback,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS.keys(), required=True)
    args = parser.parse_args()

    con = make_con()
    log(args.scenario, "triggered")
    SCENARIOS[args.scenario](con)
    log(args.scenario, "complete")
    con.close()


if __name__ == "__main__":
    main()

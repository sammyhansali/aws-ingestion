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
import json
import os
import random
import threading
from datetime import datetime, timezone

import boto3
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

S3_BUCKET = "sh26-aws-ingestion"
S3_STRESS_LOGS_PREFIX = "2-cdc-dms/stress-logs"

N_BURST = 50
N_LARGE_TXN = 5000
N_CONCURRENT_THREADS = 10
N_ROLLBACK = 20


def make_con():
    return psycopg2.connect(**DB_CONFIG)


def log(scenario: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{scenario}] {msg}")


def get_random_row_for_update(cur) -> tuple[int]:
    cur.execute(
        """
        select id, user_id
        from transactions
        order by random()
        limit 1
        ;
        """
    )
    id, user_id = cur.fetchone()
    print(f"id: {id}, user_id: {user_id}")

    return id, user_id


def scenario_burst(con) -> dict:
    """
    N_BURST rapid UPDATEs to the same row within one second.
    Expect DMS to capture all N_BURST events (at-least-once).
    Reconstruction should reflect only the final state.
    """
    # 1. pick or insert a target row, note its id
    # 2. in a tight loop, UPDATE the row N_BURST times (e.g. increment user_id each time)
    # 3. commit after each individual update
    # 4. log final user id and id

    cur = con.cursor()
    id, user_id = get_random_row_for_update(cur)
    try:
        for i in range(N_BURST):
            cur.execute(
                f"""
                update transactions
                set user_id = {user_id + i + 1}
                where id = {id}
                ;
                """
            )
            con.commit()
        log("burst", f"id: {id}, final_user_id: {user_id + N_BURST}")
    except Exception as e:
        print(f"Failed burst update. Exception: {e}")
        con.rollback()

    return {"id": id, "final_user_id": user_id + N_BURST}


def _update_worker(row_id: int, thread_idx: int) -> None:
    con = make_con()
    cur = con.cursor()
    cur.execute(
        """
        update transactions
        set user_id = %s
        where id = %s
        ;
        """,
        [thread_idx, row_id],
    )
    con.commit()
    con.close()


def scenario_concurrent(con) -> dict:
    """
    N_CONCURRENT_THREADS connections each update the same row simultaneously.
    Expect DMS to capture all updates; reconstruction should reflect the last committed state.
    """
    # 1. pick or insert a target row, note its id
    # 2. spawn N_CONCURRENT_THREADS threads, each opening its own connection
    # 3. each thread UPDATEs the same row with a different user_id and commits
    # 4. join all threads
    # 5. log  id

    cur = con.cursor()
    id, _ = get_random_row_for_update(cur)

    threads = [
        threading.Thread(target=_update_worker, args=(id, i))
        for i in range(N_CONCURRENT_THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log("concurrent", f"id={id}")
    return {"id": id}


def scenario_ghost(con) -> dict:
    """
    INSERT a row then immediately DELETE it in separate transactions before DMS flushes.
    Expect: DMS may capture both I+D, or coalesce to nothing.
    Reconstruction must not leave the row in current-state.
    """
    # 1. INSERT a new row, commit — note the id
    # 2. immediately DELETE that id, commit
    # 3. log triggered_at and id
    cur = con.cursor()
    cur.execute(
        """
        insert into transactions (user_id, amount)
        values (%s, %s)
        returning id
        ;
        """,
        [random.randint(1, 2000), random.uniform(4.99, 9999.00)],
    )
    (id,) = cur.fetchone()
    con.commit()
    cur.execute("delete from transactions where id = %s", (id,))
    con.commit()
    log("ghost", f"id={id}")
    return {"id": id}


def scenario_large_txn(con) -> dict:
    """
    Single transaction touching N_LARGE_TXN rows.
    Expect DMS to capture all rows in one batch; tests memory/buffer behavior.
    """
    # 1. open a transaction
    # 2. UPDATE N_LARGE_TXN random rows (order by random() limit N)
    # 3. commit in one shot
    # 4. log triggered_at and row count
    cur = con.cursor()
    cur.execute(
        f"""
        update transactions
        set user_id = 6742069
        where id in (
            select id
            from transactions
            order by random()
            limit {N_LARGE_TXN}
        )
        returning id
        ;
        """
    )
    updated_ids = cur.fetchall()
    con.commit()

    log("large-txn", f"rows={len(updated_ids)}")
    return {"rows": len(updated_ids)}


def scenario_rollback(con) -> dict:
    """
    Begin a transaction, UPDATE several rows, then roll back.
    DMS must NOT surface any of these changes.
    """
    # 1. open a transaction
    # 2. UPDATE several rows
    # 3. roll back
    # 4. log triggered_at — after the run, verify no events appear in change-log
    cur = con.cursor()
    cur.execute(
        f"""
        update transactions
        set user_id = 6666666
        where id in (
            select id
            from transactions
            order by random()
            limit {N_ROLLBACK}
        )
        returning id
        ;
        """
    )
    rolled_back_ids = cur.fetchall()
    con.rollback()

    log("rollback", f"rows={len(rolled_back_ids)}")
    return {"rows": len(rolled_back_ids)}


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

    triggered_at = datetime.now(timezone.utc).isoformat()
    con = make_con()
    log(args.scenario, "triggered")
    result = SCENARIOS[args.scenario](con)
    log(args.scenario, "complete")
    con.close()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")[:-3]
    payload = {"scenario": args.scenario, "triggered_at": triggered_at, **result}
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{S3_STRESS_LOGS_PREFIX}/{args.scenario}-{ts}.json",
        Body=json.dumps(payload),
    )
    print(f"logged to s3: {S3_STRESS_LOGS_PREFIX}/{args.scenario}-{ts}.json")


if __name__ == "__main__":
    main()

"""
Glue Python shell job — runs every 5 minutes.
Generates a realistic batch of OLTP changes on the transactions table.

Glue job parameters:
    --RDS_HOST, --RDS_PORT, --RDS_DB, --RDS_USER, --RDS_PASSWORD
    --S3_BUCKET, --METRICS_PREFIX
"""

import json
import os
import random
from datetime import datetime, timezone

import boto3
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("RDS_HOST"),
    "port": os.environ.get("RDS_PORT"),
    "dbname": os.environ.get("RDS_DBNAME"),
    "user": os.environ.get("RDS_USER"),
    "password": os.environ.get("RDS_PASSWORD"),
}

S3_BUCKET = "sh26-aws-ingestion"
S3_OLTP_LOGS_PREFIX = "2-cdc-dms/oltp-logs"

N_INSERTS = 20
N_UPDATES = 50
N_DELETES = 5


def insert_transactions(cur) -> list[dict]:
    """Insert N_INSERTS new transactions. Returns list of {id, committed_at}."""

    to_insert = []
    for _ in range(N_INSERTS):
        to_insert.append(
            (
                random.randint(1, 2000),
                random.uniform(4.99, 9999.00),
                random.choice(["pending", "processing", "completed", "cancelled"]),
                json.dumps({}),
            )
        )

    query = """
    insert into transactions (user_id, amount, status, metadata)
    values %s
    returning id, now()
    """
    rows = execute_values(cur, query, to_insert, fetch=True)
    metadata = [{"id": id, "committed_at": now} for id, now in rows]
    return metadata


def update_transactions(cur) -> list[dict]:
    """
    Pick N_UPDATES random existing rows and advance their status.
    Returns list of {id, old_status, new_status, committed_at}.
    """
    STATUS_TRANSITIONS = {
        "pending": "processing",
        "processing": random.choice(["completed", "cancelled"]),
        "completed": "pending",
        "cancelled": "pending",
    }
    cur.execute(
        f"""
        select id, status
        from transactions
        order by random()
        limit {N_UPDATES}
        ;
        """
    )
    rows = cur.fetchall()
    to_update = [(STATUS_TRANSITIONS[status], id) for id, status in rows]

    query = """
        update transactions
        set
            status = data.new_status
        from (values %s) as data(new_status, id)
        where transactions.id = data.id::int
        returning transactions.id, now()
    """
    updated = execute_values(
        cur,
        query,
        to_update,
        fetch=True,
    )
    old_status_map = {id: status for id, status in rows}
    metadata = [
        {
            "id": id,
            "old_status": old_status_map[id],
            "new_status": STATUS_TRANSITIONS[old_status_map[id]],
            "committed_at": now,
        }
        for id, now in updated
    ]
    return metadata


def delete_transactions(cur) -> list[dict]:
    """
    Pick N_DELETES random completed/cancelled rows and hard delete them.
    Returns list of {id, committed_at}.
    """
    cur.execute(
        f"""
        delete from transactions
        where id in (
            select id
            from transactions
            order by random()
            limit {N_DELETES}
        )
        returning id, now()
        ;
        """
    )
    deleted = cur.fetchall()
    metadata = [{"id": id, "committed_at": ca} for id, ca in deleted]
    return metadata


def log_committed(records: list[dict], operation: str) -> None:
    """Print committed_at log entries for lag analysis."""
    for r in records:
        print(
            json.dumps(
                {"op": operation, **r, "committed_at": r["committed_at"].isoformat()}
            )
        )


def write_logs_to_s3(s3, inserts: list[dict], updates: list[dict], deletes: list[dict]) -> None:
    """Write all committed records for this run as a JSONL file to S3."""
    lines = []
    for op, records in [("I", inserts), ("U", updates), ("D", deletes)]:
        for r in records:
            lines.append(json.dumps({"op": op, **r, "committed_at": r["committed_at"].isoformat()}))

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")[:-3]
    key = f"{S3_OLTP_LOGS_PREFIX}/{ts}.jsonl"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body="\n".join(lines))
    print(f"logged to s3: {key}")


def iud(con, cur, fn) -> list[dict]:
    try:
        output = fn(cur)
        con.commit()
    except Exception as e:
        con.rollback()
        raise e

    return output


def main():
    con = psycopg2.connect(**DB_CONFIG)
    cur = con.cursor()

    inserts = iud(con, cur, insert_transactions)
    updates = iud(con, cur, update_transactions)
    deletes = iud(con, cur, delete_transactions)

    log_committed(inserts, "I")
    log_committed(updates, "U")
    log_committed(deletes, "D")

    s3 = boto3.client("s3")
    write_logs_to_s3(s3, inserts, updates, deletes)

    cur.close()
    con.close()


if __name__ == "__main__":
    main()

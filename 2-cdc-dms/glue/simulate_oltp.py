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

N_INSERTS = 20
N_UPDATES = 50
N_DELETES = 5

STATUS_TRANSITIONS = {
    "pending": "processing",
    "processing": random.choice(["completed", "cancelled"]),
}


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
    rows = [{"id": id, "committed_at": now} for id, now in rows]
    return rows


def update_transactions(cur) -> list[dict]:
    """
    Pick N_UPDATES random existing rows and advance their status.
    Returns list of {id, old_status, new_status, committed_at}.
    """
    pass


def delete_transactions(cur) -> list[dict]:
    """
    Pick N_DELETES random completed/cancelled rows and hard delete them.
    Returns list of {id, committed_at}.
    """
    pass


def log_committed(records: list[dict], operation: str) -> None:
    """Print committed_at log entries for lag analysis."""
    pass


def iud(con, cur, fn) -> list[dict]:
    try:
        output = fn(cur)
        print(output)
        con.commit()
    except Exception:
        con.rollback()

    return output


def main():
    con = psycopg2.connect(**DB_CONFIG)
    cur = con.cursor()

    inserts = iud(con, cur, insert_transactions)
    # updates = update_transactions(cur)
    # deletes = delete_transactions(cur)
    # con.commit()

    # log_committed(inserts, "I")
    # log_committed(updates, "U")
    # log_committed(deletes, "D")

    cur.close()
    con.close()


if __name__ == "__main__":
    main()

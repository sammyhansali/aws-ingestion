"""
Seed the RDS transactions table with initial rows before starting DMS.
Run once: python seed_table.py

Env vars required:
    RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
"""

import argparse
import csv
import io
import json
import os
import random

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "local": {
        "host": os.environ.get("LOCALDB_HOST"),
        "port": os.environ.get("LOCALDB_PORT"),
        "dbname": os.environ.get("LOCALDB_DBNAME"),
        "user": os.environ.get("LOCALDB_USER"),
        "password": os.environ.get("LOCALDB_PASSWORD"),
    },
    "rds": {
        "host": os.environ.get("RDS_HOST"),
        "port": os.environ.get("RDS_PORT"),
        "dbname": os.environ.get("RDS_DBNAME"),
        "user": os.environ.get("RDS_USER"),
        "password": os.environ.get("RDS_PASSWORD"),
    },
}
N_RECORDS = 10_000


def already_seeded_truncate(cur) -> None:
    cur.execute("select count(*) from transactions;")
    if cur.fetchone()[0] > 0:
        print("Detected existing transactions data. Truncating...")
        cur.execute("truncate table transactions restart identity;")
        print("Truncation complete.")


def seed_table(cur) -> None:
    sources = ["web", "mobile", "api", "pos", "partner"]
    regions = ["US", "CA", "GB", "AU", "DE", "FR"]
    channels = ["organic", "referral", "paid", "direct"]

    buf = io.StringIO()
    writer = csv.writer(buf)

    for i in range(N_RECORDS):
        metadata = {}
        metadata_options = [
            ("sources", random.choice(sources)),
            ("regions", random.choice(regions)),
            ("channels", random.choice(channels)),
        ]
        idx = i % 4
        for k, v in metadata_options[:idx]:
            metadata[k] = v

        writer.writerow(
            [
                random.randint(1, 2000),
                random.uniform(4.99, 9999.00),
                random.choice(["pending", "processing", "completed", "cancelled"]),
                json.dumps(metadata),
            ]
        )
    buf.seek(0)
    cur.copy_expert(
        "copy transactions (user_id, amount, status, metadata) from stdin with csv ",
        buf,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "rds"], default="rds")
    args = parser.parse_args()

    con = psycopg2.connect(**DB_CONFIG[args.env])
    cur = con.cursor()

    already_seeded_truncate(cur)

    print("Seeding transactions table...")
    try:
        seed_table(cur)
        con.commit()
        print("Seeding complete.")
    except Exception as e:
        print(f"Error seeding transactions table: {e}")
        con.rollback()

    cur.close()
    con.close()

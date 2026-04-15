import argparse

import boto3
import psycopg2
from botocore.exceptions import ClientError
from seed_tables import (
    DB_CONFIGS,
    IDXS,
    seed_customers,
    seed_order_items,
    seed_orders,
    seed_products,
)

S3_BUCKET = "sh26-aws-ingestion-tf"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental"
TRIGGERS = ["recurring_simulate_changes", "on_simulate_ingest"]
S3_PREFIXES_TO_DELETE = [
    f"{S3_PREFIX}/raw/",
    f"{S3_PREFIX}/processing/",
    f"{S3_PREFIX}/metrics/",
    f"{S3_PREFIX}/incremental_checkpoint.json",
]


def stop_triggers():
    glue = boto3.client("glue", region_name="us-east-1")
    for name in TRIGGERS:
        print(f"Stopping trigger: {name}...")
        try:
            glue.stop_trigger(Name=name)
            print("  Stopped")
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidStateException":
                print("  Already stopped")
            else:
                raise


def delete_s3_data():
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    for prefix in S3_PREFIXES_TO_DELETE:
        print(f"Deleting s3://{S3_BUCKET}/{prefix}...")
        to_delete = [
            {"Key": obj["Key"]}
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix)
            for obj in page.get("Contents", [])
        ]
        if to_delete:
            s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": to_delete})
            print(f"  Deleted {len(to_delete)} objects")
        else:
            print("  Nothing to delete")


def truncate_tables(conn):
    print("Truncating tables...")
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE customers, products, orders, order_items CASCADE;")
    conn.commit()
    cur.close()
    print("  Done")


def reseed(conn, idx):
    cur = conn.cursor()
    for table, fn in [
        ("customers", seed_customers),
        ("products", seed_products),
        ("orders", seed_orders),
        ("order_items", seed_order_items),
    ]:
        print(f"Seeding {table}...")
        try:
            fn(cur, idx)
            conn.commit()
            print("  Done")
        except Exception as e:
            print(f"  Error: {e}")
            conn.rollback()
    cur.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "rds"], default="rds")
    parser.add_argument("--reseed", action="store_true")
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args = parser.parse_args()

    stop_triggers()
    delete_s3_data()

    conn = psycopg2.connect(**DB_CONFIGS[args.env])
    truncate_tables(conn)

    if args.reseed:
        reseed(conn, IDXS[args.size])

    conn.close()
    print("Reset complete.")

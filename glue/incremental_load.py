import argparse
import io
import json
from datetime import datetime, timezone

import boto3
import metrics
import pandas as pd
import psycopg2

DB_CONFIG = {
    "host": "database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "dbname": "postgres",
    "user": "REDACTED_USER",
    "password": "REDACTED",
}

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental"
RAW_PREFIX = f"{S3_PREFIX}/raw/incremental"
PROCESSING_PREFIX = f"{S3_PREFIX}/processing/incremental"
CHECKPOINT_KEY = f"{S3_PREFIX}/incremental_checkpoint.json"

TABLES = ["customers", "products", "orders", "order_items"]

s3 = boto3.client("s3")


def get_last_run_timestamp() -> str:
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=CHECKPOINT_KEY)
        checkpoint = json.loads(obj["Body"].read())
        return checkpoint["last_run_timestamp"]
    except Exception:
        # first run — use epoch start to get all rows
        return "1970-01-01 00:00:00"


def save_checkpoint(timestamp: str):
    checkpoint = {"last_run_timestamp": timestamp}
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=CHECKPOINT_KEY,
        Body=json.dumps(checkpoint),
    )


def extract(table: str, last_run_timestamp: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    sql = f"select * from {table} where updated_at > '{last_run_timestamp}';"
    df = pd.read_sql(sql, conn)
    return df


def write_raw(df: pd.DataFrame, table: str, run_timestamp: str):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{RAW_PREFIX}/{table}/run_ts={run_timestamp}/{table}.csv",
        Body=csv_buffer.getvalue(),
    )


def write_processing(df: pd.DataFrame, table: str, run_timestamp: str):
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{PROCESSING_PREFIX}/{table}/run_ts={run_timestamp}/data.parquet",
        Body=parquet_buffer.getvalue(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args, _ = parser.parse_known_args()

    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    s3_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    last_run_timestamp = get_last_run_timestamp()
    print(f"Incremental load — changes since: {last_run_timestamp}")

    for table in TABLES:
        print(f"Processing {table}...")
        with metrics.measure() as m:
            df = extract(table, last_run_timestamp)
            write_raw(df, table, s3_timestamp)
            write_processing(df, table, s3_timestamp)

        metrics.log(
            job_type="incremental",
            dataset_size=args.size,
            table=table,
            rows_processed=len(df),
            source_row_count=None,
            target_row_count=None,
            **m,
        )
        print(f"Done: {table} ({len(df)} rows)")

    save_checkpoint(run_timestamp)  # uses colon format for SQL compatibility
    print(f"Checkpoint saved: {run_timestamp}")

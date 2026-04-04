import argparse
import io
from datetime import datetime, timezone

import boto3
import pandas as pd
import psycopg2

import metrics

DB_CONFIG = {
    "host": "database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "dbname": "postgres",
    "user": "REDACTED_USER",
    "password": "REDACTED",
}

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental"
RAW_PREFIX = f"{S3_PREFIX}/raw"
PROCESSING_PREFIX = f"{S3_PREFIX}/processing"

TABLES = ["customers", "products", "orders", "order_items"]

s3 = boto3.client("s3")


def extract(table: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    sql = f"SELECT * FROM {table}"
    df = pd.read_sql(sql, conn)
    return df


def write_raw(df: pd.DataFrame, table: str):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{RAW_PREFIX}/{table}.csv",
        Body=csv_buffer.getvalue(),
    )


def write_processing(df: pd.DataFrame, table: str):
    ingestion_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{PROCESSING_PREFIX}/{table}/ingestion_ts={ingestion_timestamp}/data.parquet",
        Body=parquet_buffer.getvalue(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args = parser.parse_args()

    for table in TABLES:
        print(f"Processing {table}...")
        with metrics.measure() as m:
            df = extract(table)
            write_raw(df, table)
            write_processing(df, table)

        metrics.log(
            job_type="full",
            dataset_size=args.size,
            table=table,
            rows_processed=len(df),
            source_row_count=len(df),
            target_row_count=len(df),
            **m,
        )
        print(f"Done: {table} ({len(df)} rows)")

import argparse
import io
import json

import boto3
import metrics
import pandas as pd
import psycopg2

_secret = boto3.client("secretsmanager", region_name="us-east-1").get_secret_value(
    SecretId="1-batch-ingestion/rds-credentials"
)
DB_CONFIG = json.loads(_secret["SecretString"])

S3_BUCKET = "sh26-aws-ingestion-tf"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental"
RAW_PREFIX = f"{S3_PREFIX}/raw/full"
PROCESSING_PREFIX = f"{S3_PREFIX}/processing/full"

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
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{PROCESSING_PREFIX}/{table}/data.parquet",
        Body=parquet_buffer.getvalue(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args, _ = parser.parse_known_args()

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

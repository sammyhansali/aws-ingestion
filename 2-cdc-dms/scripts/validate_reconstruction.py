"""
Validates that current-state Parquet in S3 matches live RDS transactions table.
Run after any Glue reconstruction job run.

Usage:
    python validate_reconstruction.py --bucket <bucket>

Env vars required:
    RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
"""

import io
import json
import os

import boto3
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "2-cdc-dms"
CURRENT_STATE_PREFIX = f"{S3_PREFIX}/current-state"
DB_CONFIG = {
    "host": os.environ.get("RDS_HOST"),
    "port": os.environ.get("RDS_PORT"),
    "dbname": os.environ.get("RDS_DBNAME"),
    "user": os.environ.get("RDS_USER"),
    "password": os.environ.get("RDS_PASSWORD"),
}


def read_current_state(s3) -> pd.DataFrame:
    """Read current-state Parquet from S3."""
    obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{CURRENT_STATE_PREFIX}/data.parquet")
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
    return df


def read_oltp(con) -> pd.DataFrame:
    df = pd.read_sql("select * from transactions;", con)
    con.close()
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["amount"] = df["amount"].astype(float)
    df["metadata"] = df["metadata"].apply(
        lambda x: json.dumps(x) if isinstance(x, dict) else x
    )
    for col in ["created_at", "updated_at"]:
        if df[col].dtype == "datetime64[us]":
            df[col] = df[col].dt.tz_localize("UTC")
    return df.sort_values("id").reset_index(drop=True)


def diff(parquet: pd.DataFrame, rds: pd.DataFrame) -> None:
    parquet = normalize(parquet)
    rds = normalize(rds)

    print(f"Parquet rows: {len(parquet)} | RDS rows: {len(rds)}")

    merged = parquet.merge(
        rds, on="id", how="outer", indicator=True, suffixes=("_parquet", "_rds")
    )

    only_in_parquet = merged[merged["_merge"] == "left_only"][["id"]]
    only_in_rds = merged[merged["_merge"] == "right_only"][["id"]]
    print(f"Only in parquet (should be deleted in RDS): {len(only_in_parquet)}")
    print(f"Only in RDS (missed by reconstruction): {len(only_in_rds)}")
    if not only_in_parquet.empty:
        print(only_in_parquet)
    if not only_in_rds.empty:
        print(only_in_rds)

    cols = [c for c in parquet.columns if c != "id"]
    in_both = merged[merged["_merge"] == "both"]
    mismatches = in_both[
        [c for c in in_both.columns if c.endswith("_parquet") or c.endswith("_rds")]
    ]
    parquet_vals = in_both[[f"{c}_parquet" for c in cols]].rename(
        columns=lambda x: x.removesuffix("_parquet")
    )
    rds_vals = in_both[[f"{c}_rds" for c in cols]].rename(
        columns=lambda x: x.removesuffix("_rds")
    )
    col_diff = parquet_vals.compare(rds_vals, result_names=("parquet", "rds"))
    print(f"Column-level mismatches in shared rows: {len(col_diff)}")
    if not col_diff.empty:
        print(col_diff)


def main():
    s3 = boto3.client("s3")
    current_state = read_current_state(s3)

    con = psycopg2.connect(**DB_CONFIG)
    oltp = read_oltp(con)

    diff(current_state, oltp)


if __name__ == "__main__":
    main()

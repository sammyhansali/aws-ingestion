"""
One-time audit of DMS S3 output.
Reads sample LOAD and CDC files, prints schema, op code distribution,
column completeness, and type fidelity.

Usage: python inspect_dms_output.py --bucket <bucket> --prefix change-log/
"""

import argparse
import os

import duckdb
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "2-cdc-dms/change-log/public/transactions"


def make_con():
    con = duckdb.connect()
    con.execute("install httpfs; load httpfs;")
    con.execute(
        f"""
        create or replace secret secret (
            type s3,
            provider config,
            key_id '{os.environ["AWS_ACCESS_KEY_ID"]}',
            secret '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            region 'us-east-1'
        )
        """
    )
    return con


def inspection(cur) -> None:
    col_types = {
        "op": "varchar(1)",
        "id": "integer",
        "user_id": "integer",
        "amount": "numeric(10,2)",
        "status": "varchar(20)",
        "metadata": "json",
        "version": "integer",
        "created_at": "timestamptz",
        "updated_at": "timestamptz",
    }
    cols = list(col_types.keys())

    cdc_df = cur.execute(
        f"""
        select *
        from read_csv('s3://{S3_BUCKET}/{S3_PREFIX}/2026*.csv', names={cols}, types={col_types})
        """
    ).df()
    print(cdc_df.head())

    del col_types["op"]
    cols = cols[1:]

    load_df = cur.execute(
        f"""
        select *
        from read_csv('s3://{S3_BUCKET}/{S3_PREFIX}/LOAD*.csv', names={cols}, types={col_types})
        """
    ).df()
    print(load_df.head())

    # Schema inspection
    print("\n---------SCHEMA INSPECTION---------")
    print(cdc_df.dtypes)
    print(cdc_df.isnull().sum())

    # Op code distribution
    print("\n---------OP CODE DISTRIBUTION---------")
    print(cdc_df["op"].value_counts())

    # Sample rows per op type
    print("\n---------SAMPLE ROW PER OP TYPE---------")
    for op in cdc_df["op"].unique():
        print(f"\nCURRENT OP: {op}\n")
        print(cdc_df[cdc_df["op"] == op].iloc[0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=S3_BUCKET)
    parser.add_argument("--prefix", default=S3_PREFIX)
    args = parser.parse_args()

    con = make_con()
    cur = con.cursor()
    inspection(cur)

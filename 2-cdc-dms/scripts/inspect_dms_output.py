"""
One-time audit of DMS S3 output.
Reads sample LOAD and CDC files, prints schema, op code distribution,
column completeness, and type fidelity.

Usage: python inspect_dms_output.py --bucket <bucket> --prefix change-log/
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from dms_io import make_con, read_cdc_files, read_load_files

load_dotenv()

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "2-cdc-dms/change-log/public/transactions"


def inspection(cur) -> None:
    cdc_df = read_cdc_files(cur, f"s3://{S3_BUCKET}/{S3_PREFIX}/2026*.csv")
    print(cdc_df.head())

    load_df = read_load_files(cur, f"s3://{S3_BUCKET}/{S3_PREFIX}/LOAD*.csv")
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

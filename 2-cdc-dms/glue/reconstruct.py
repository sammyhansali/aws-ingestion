"""
Glue Python shell job — runs every 5 minutes.
Reads new DMS change-log files from S3, applies op codes (I/U/D) to
current-state Parquet, and advances the watermark.

Glue job parameters:
    --S3_BUCKET, --CHANGE_LOG_PREFIX, --CURRENT_STATE_PREFIX, --WATERMARK_KEY
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import boto3
import pandas as pd
from dms_io import make_con
from dms_io import read_cdc_files as _read_cdc_files
from dms_io import read_load_files as _read_load_files
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = "sh26-aws-ingestion"
S3_PREFIX = "2-cdc-dms"
CHANGE_LOG_PREFIX = f"{S3_PREFIX}/change-log/public/transactions"
CURRENT_STATE_PREFIX = f"{S3_PREFIX}/current-state"
WATERMARK_KEY = f"{S3_PREFIX}/watermark.json"


def load_watermark(s3) -> str | None:
    """Read watermark JSON from S3. Returns last processed file key or None (first run)."""
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=WATERMARK_KEY)
        watermark = json.loads(obj["Body"].read())
        return watermark
    except Exception:
        # print(f"No watermark found. Exception: {e}")
        return None


def save_watermark(s3, last_key: str) -> None:
    """Write {"last_key": "..."} back to S3."""
    body = {"last_key": last_key}
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=WATERMARK_KEY,
        Body=json.dumps(body),
    )


def load_seed_data() -> pd.DataFrame:
    """Read all LOAD*.csv files for initial seed, adds op='I'."""
    con = make_con()
    df = _read_load_files(
        con.cursor(), f"s3://{S3_BUCKET}/{CHANGE_LOG_PREFIX}/LOAD*.csv"
    )
    con.close()
    return df


def list_cdc_files(s3, since_key: str | None) -> list[str]:
    """Return S3 URIs for CDC files with key > since_key, in lexicographic order."""
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=f"{CHANGE_LOG_PREFIX}/")
    # print([o["Key"] for o in resp.get("Contents", [])])
    keys = [
        o["Key"]
        for o in resp.get("Contents", [])
        if not o["Key"].split("/")[-1].startswith("LOAD")
        and (since_key is None or o["Key"] > since_key)
    ]
    keys.sort()
    return [f"s3://{S3_BUCKET}/{k}" for k in keys]


def get_cdc_files(s3, since_key: str | None) -> pd.DataFrame:
    """Read CDC files newer than since_key. Returns empty DataFrame if none."""
    keys = list_cdc_files(s3, since_key)
    if not keys:
        return None, None
    con = make_con()
    df = _read_cdc_files(con.cursor(), keys)
    con.close()
    last_key = keys[-1].removeprefix(f"s3://{S3_BUCKET}/")
    return df, last_key


def apply_ops(current_df, changes_df) -> pd.DataFrame:
    """
    Apply changes in WAL order:
      I → append row
      U → overwrite by id
      D → drop by id
    """
    df = changes_df.drop_duplicates(subset="id", keep="last")
    to_upsert = df[df["op"].isin(["I", "U"])]
    changed_ids = df["id"]

    current_df = current_df[~current_df["id"].isin(changed_ids)]
    current_df = pd.concat([current_df, to_upsert]).drop(columns="op")

    return current_df


def read_current_state(s3) -> pd.DataFrame:
    """Read current-state Parquet from S3."""
    obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{CURRENT_STATE_PREFIX}/data.parquet")
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
    return df


def write_current_state(s3, df) -> None:
    """Write DataFrame as partitioned Parquet to current-state/ in S3."""
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{CURRENT_STATE_PREFIX}/data.parquet",
        Body=parquet_buffer.getvalue(),
    )


def main():
    # Parse Glue job parameters: S3_BUCKET, CHANGE_LOG_PREFIX, CURRENT_STATE_PREFIX, WATERMARK_KEY

    s3 = boto3.client("s3")

    watermark = load_watermark(s3)
    print(watermark)
    if watermark is None:
        df = load_seed_data()
        write_current_state(s3, df)
        save_watermark(s3, last_key=None)
    else:
        current_df = read_current_state(s3)
        changes_df, last_cdc_key = get_cdc_files(s3, since_key=watermark["last_key"])
        if (changes_df is None) or (changes_df.empty):
            return
        new_df = apply_ops(current_df, changes_df)
        write_current_state(s3, new_df)
        save_watermark(s3, last_key=last_cdc_key)


if __name__ == "__main__":
    main()

import io
import tracemalloc
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter

import boto3
import pandas as pd
from botocore.exceptions import ClientError

S3_BUCKET = "sh26-aws-ingestion-tf"
METRICS_KEY = "1-batch-ingestion-full-vs-incremental/metrics/metrics.csv"

GLUE_DPU = 0.0625
GLUE_DPU_PRICE_PER_HOUR = 0.44

s3 = boto3.client("s3")

COLUMNS = [
    "run_timestamp",
    "job_type",
    "dataset_size",
    "table",
    "rows_processed",
    "runtime_seconds",
    "memory_peak_mb",
    "estimated_cost_usd",
    "source_row_count",
    "target_row_count",
]


@contextmanager
def measure():
    """Context manager that yields a dict populated with runtime and memory after the block exits."""
    result = {}
    tracemalloc.start()
    start = perf_counter()
    yield result
    result["runtime_seconds"] = round(perf_counter() - start, 3)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result["memory_peak_mb"] = round(peak / 1024 / 1024, 3)
    result["estimated_cost_usd"] = round(
        (result["runtime_seconds"] / 3600) * GLUE_DPU * GLUE_DPU_PRICE_PER_HOUR, 6
    )


def log(
    job_type: str,
    dataset_size: str,
    table: str,
    rows_processed: int,
    runtime_seconds: float,
    memory_peak_mb: float,
    estimated_cost_usd: float,
    source_row_count: int,
    target_row_count: int,
):
    row = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "job_type": job_type,
        "dataset_size": dataset_size,
        "table": table,
        "rows_processed": rows_processed,
        "runtime_seconds": runtime_seconds,
        "memory_peak_mb": memory_peak_mb,
        "estimated_cost_usd": estimated_cost_usd,
        "source_row_count": source_row_count,
        "target_row_count": target_row_count,
    }

    try:
        # load existing CSV if it exists, otherwise start fresh
        try:
            obj = s3.get_object(Bucket=S3_BUCKET, Key=METRICS_KEY)
            existing = pd.read_csv(io.BytesIO(obj["Body"].read()))
            print(f"Loaded existing metrics CSV ({len(existing)} rows)")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                print("No existing metrics CSV found, starting fresh")
                existing = pd.DataFrame(columns=COLUMNS)
            else:
                raise

        updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)

        buf = io.BytesIO()
        updated.to_csv(buf, index=False)
        s3.put_object(Bucket=S3_BUCKET, Key=METRICS_KEY, Body=buf.getvalue())
        print(f"Metrics logged for {table}")
    except Exception as e:
        print(f"ERROR in metrics.log: {e}")

"""
Shared DuckDB S3 connection and DMS file reading utilities.
Used by inspect_dms_output.py and reconstruct.py.
"""

import os

import duckdb
import pandas as pd

CDC_COL_TYPES = {
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
LOAD_COL_TYPES = {k: v for k, v in CDC_COL_TYPES.items() if k != "op"}

CDC_COLS = list(CDC_COL_TYPES.keys())
LOAD_COLS = list(LOAD_COL_TYPES.keys())


def make_con() -> duckdb.DuckDBPyConnection:
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


def read_load_files(cur, s3_glob: str) -> pd.DataFrame:
    """Read LOAD CSV files matching s3_glob. Adds op='I' column."""
    df = cur.execute(
        f"select * from read_csv('{s3_glob}', names={LOAD_COLS}, types={LOAD_COL_TYPES})"
    ).df()
    return df


def read_cdc_files(cur, s3_paths: "str | list[str]") -> pd.DataFrame:
    """
    Read CDC CSV files. s3_paths is either a glob string or a list of S3 URIs.
    Returns rows sorted by filename order (WAL order is preserved within each file).
    """
    if isinstance(s3_paths, list):
        path_expr = str(s3_paths)
    else:
        path_expr = f"'{s3_paths}'"
    return cur.execute(
        f"select * from read_csv({path_expr}, names={CDC_COLS}, types={CDC_COL_TYPES})"
    ).df()

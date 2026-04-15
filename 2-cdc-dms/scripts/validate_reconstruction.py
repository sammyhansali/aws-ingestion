"""
Validates that current-state Parquet in S3 matches live RDS transactions table.
Run after any Glue reconstruction job run.

Usage:
    python validate_reconstruction.py --bucket <bucket>

Env vars required:
    RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
"""

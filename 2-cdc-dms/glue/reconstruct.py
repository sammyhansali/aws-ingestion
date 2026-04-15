"""
Glue Python shell job — runs every 5 minutes.
Reads new DMS change-log files from S3, applies op codes (I/U/D) to
current-state Parquet, and advances the watermark.

Glue job parameters:
    --S3_BUCKET, --CHANGE_LOG_PREFIX, --CURRENT_STATE_PREFIX, --WATERMARK_KEY
"""

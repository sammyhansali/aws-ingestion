"""
Glue Python shell job — runs every 5 minutes.
Generates a realistic batch of OLTP changes on the transactions table.

Glue job parameters:
    --RDS_HOST, --RDS_PORT, --RDS_DB, --RDS_USER, --RDS_PASSWORD
    --S3_BUCKET, --METRICS_PREFIX
"""

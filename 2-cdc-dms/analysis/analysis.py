"""
Post-run analysis of CDC pipeline metrics.
Reads DMS change-log, committed_at logs, and current-state Parquet.
Outputs:
  - lag_table.txt          — p50/p95/p99 lag by op type
  - duplicates.txt         — duplicate event count and rate
  - event_trace.png        — timeline of change events

Usage: python analysis.py --bucket <bucket> --output-dir analysis/output/
"""

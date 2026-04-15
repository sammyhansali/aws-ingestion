"""
One-time audit of DMS S3 output.
Reads sample LOAD and CDC files, prints schema, op code distribution,
column completeness, and type fidelity.

Usage: python inspect_dms_output.py --bucket <bucket> --prefix change-log/
"""

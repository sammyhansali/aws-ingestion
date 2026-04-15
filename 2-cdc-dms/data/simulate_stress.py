"""
Stress experiments targeting DMS edge cases.
Run manually, one scenario at a time.

Scenarios:
  --scenario burst        50+ rapid UPDATEs to same row within 1 second
  --scenario concurrent   Multiple connections updating same row simultaneously
  --scenario ghost        INSERT immediately followed by DELETE before DMS flush
  --scenario large-txn    Single transaction touching 5000 rows
  --scenario rollback     Write changes then roll back; DMS must NOT surface these

Env vars required:
    RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD
"""

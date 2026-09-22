"""
Triggers and verifies one fresh off-volume backup immediately before
running scripts/repair_leaked_seed_events.py with REPAIR_MODE=apply.

Calls the existing, already-tested app.db.remote_backup.backup_to_bucket
(CR-0b) directly — never touches the live database itself; it only
reads it via SQLite's own online-backup API. Exits non-zero (and prints
the full result) if the backup does not reach `remote_verified`, so a
caller scripting "run this, then run the repair" fails closed rather
than proceeding on an unverified or missing backup.

Piped the same way as the repair script: `railway ssh "python3 -" < this_file`.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    sys.path.insert(0, "/app")
    from app.db.remote_backup import backup_to_bucket

    result = backup_to_bucket("pre_seed_fixture_repair")
    print(json.dumps(result, indent=2, default=str))

    if result.get("status") != "ok" or not result.get("remote_verified"):
        print("BACKUP NOT VERIFIED — do not proceed with REPAIR_MODE=apply")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

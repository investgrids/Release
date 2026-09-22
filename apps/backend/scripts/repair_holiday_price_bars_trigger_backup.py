"""
Triggers and verifies one fresh off-volume backup immediately before
running scripts/repair_holiday_price_bars.py with REPAIR_MODE=apply.

Same pattern as scripts/repair_leaked_seed_events_trigger_backup.py —
calls the existing, already-tested app.db.remote_backup.backup_to_bucket
(CR-0b) directly, never touches the live database itself. Exits non-
zero if the backup does not reach `remote_verified`.

Piped the same way: `railway ssh "python3 -" < this_file`.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    sys.path.insert(0, "/app")
    from app.db.remote_backup import backup_to_bucket

    result = backup_to_bucket("pre_holiday_price_bar_repair")
    print(json.dumps(result, indent=2, default=str))

    if result.get("status") != "ok" or not result.get("remote_verified"):
        print("BACKUP NOT VERIFIED — do not proceed with REPAIR_MODE=apply")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

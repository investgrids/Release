"""
Recover hero images after the migration. The database was restored but the image FILES (/data/media on the old Railway volume) were not copied, so 'generated' rows point
at files that do not exist and the pages would show broken images.

Run INSIDE the backend container:   docker exec -i marketripple-backend-1 python - <args> < media_requeue.py
  (no args)           dry run: print what would change, change nothing
  --mark-lost         step 1: rows with status 'generated' whose file is missing become 'lost_file'. The API only returns a hero for status 'generated', so the site shows its
                      normal gradient fallback instead of a broken image; the image worker only picks 'pending'/'failed', so these are left alone until step 2.
  --requeue N         step 2: the newest N 'lost_file' rows become 'pending' (attempts 0, url cleared); the worker regenerates them (3 per minute, free Pollinations).
Idempotent and bounded. Every run prints before/after counts (the artifact). Take a verified backup first (scripts/backup_now.sh).
"""
import os, sqlite3, sys, json, datetime

args = sys.argv[1:]
mark = "--mark-lost" in args
requeue = int(args[args.index("--requeue") + 1]) if "--requeue" in args else 0
apply = mark or requeue > 0

con = sqlite3.connect("/data/ig.db", timeout=60)
con.execute("pragma busy_timeout=60000")
counts = lambda: dict(con.execute("select status, count(*) from generated_media group by status").fetchall())
before = counts()

def file_exists(url):
    return bool(url) and os.path.exists(os.path.join("/data/media", os.path.basename(str(url))))

result = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "mode": "apply" if apply else "dry-run", "before": before}

gen = con.execute("select id, url from generated_media where status='generated'").fetchall()
missing = [r[0] for r in gen if not file_exists(r[1])]
result["generated_rows"], result["generated_but_file_missing"] = len(gen), len(missing)

if mark and missing:
    con.executemany("update generated_media set status='lost_file' where id=? and status='generated'", [(i,) for i in missing])
    con.commit()
    result["marked_lost"] = len(missing)

if requeue:
    rows = con.execute("select id from generated_media where status='lost_file' order by coalesce(generated_at, created_at) desc limit ?", (requeue,)).fetchall()
    con.executemany("update generated_media set status='pending', attempts=0, url=NULL, error=NULL where id=? and status='lost_file'", rows)
    con.commit()
    result["requeued"] = len(rows)

result["after"] = counts()
print(json.dumps(result, indent=1))

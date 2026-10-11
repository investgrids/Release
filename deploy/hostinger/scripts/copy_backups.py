"""
Copy the off-box database backups from one S3-compatible bucket to another (Railway Bucket -> Cloudflare R2), with verification. Runs in a python:3.11-slim container with boto3 on the VPS.
  SRC_ENDPOINT SRC_REGION SRC_BUCKET SRC_KEY_ID SRC_SECRET       the bucket to copy FROM
  DST_ENDPOINT DST_REGION DST_BUCKET DST_KEY_ID DST_SECRET       the bucket to copy TO
Arguments:   (none) dry run: list what would be copied      --execute  copy      --limit N  only the N oldest missing objects (for tests)
Safe by design: never deletes anything anywhere; skips objects already present at the destination with the same size; copies OLDEST FIRST so the destination's
LastModified order matches the original order (the app's retention rule picks "the newest 5 boot backups" by that time); streams each object through a temp file, computes its SHA-256 while
downloading, compares it with the checksum the app recorded at upload (`source-sha256` metadata) when there is one, preserves the metadata, then re-reads the destination's size.
"""
import hashlib, os, sys, tempfile
import boto3
from botocore.config import Config

def client(prefix):
    return boto3.client("s3", endpoint_url=os.environ[prefix + "_ENDPOINT"], region_name=os.environ.get(prefix + "_REGION") or "auto",
                        aws_access_key_id=os.environ[prefix + "_KEY_ID"], aws_secret_access_key=os.environ[prefix + "_SECRET"],
                        config=Config(s3={"addressing_style": os.environ.get(prefix + "_ADDRESSING", "virtual" if prefix == "SRC" else "path")}, retries={"max_attempts": 5}))

def listing(c, bucket):
    out = {}
    for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for o in page.get("Contents", []):
            out[o["Key"]] = o
    return out

args = sys.argv[1:]
execute = "--execute" in args
limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
src, dst = client("SRC"), client("DST")
sb, db = os.environ["SRC_BUCKET"], os.environ["DST_BUCKET"]
s, d = listing(src, sb), listing(dst, db)
todo = sorted((o for k, o in s.items() if k not in d or d[k]["Size"] != o["Size"]), key=lambda o: o["LastModified"])
if limit:
    todo = todo[:limit]
GB = 1e9
print("source: %d objects %.1f GB | destination: %d objects | to copy: %d objects %.1f GB%s" % (len(s), sum(o["Size"] for o in s.values()) / GB, len(d), len(todo), sum(o["Size"] for o in todo) / GB, "  (--limit %d)" % limit if limit else ""))
if not execute:
    for o in todo[:8]: print("  would copy", o["Key"], "%.0f MB" % (o["Size"] / 1e6))
    print("DRY RUN: nothing copied. Add --execute to copy.")
    sys.exit(0)

ok = bad = 0
for o in todo:
    key = o["Key"]
    head = src.head_object(Bucket=sb, Key=key)
    meta = head.get("Metadata") or {}
    with tempfile.NamedTemporaryFile(dir="/work", delete=True) as tmp:
        src.download_fileobj(sb, key, tmp)
        tmp.flush()
        h = hashlib.sha256()
        tmp.seek(0)
        for chunk in iter(lambda: tmp.read(1 << 20), b""):
            h.update(chunk)
        got = h.hexdigest()
        recorded = meta.get("source-sha256")
        size = os.path.getsize(tmp.name)
        if size != head["ContentLength"] or (recorded and recorded != got):
            print("  FAIL (source object does not match its recorded checksum/size, NOT copied):", key); bad += 1; continue
        tmp.seek(0)
        dst.upload_fileobj(tmp, db, key, ExtraArgs={"Metadata": meta})
    if dst.head_object(Bucket=db, Key=key)["ContentLength"] != size:
        print("  FAIL (destination size differs):", key); bad += 1; continue
    ok += 1
    print("  copied %s  %.0f MB  sha256 %s%s" % (key, size / 1e6, got[:12], "  (matches recorded)" if recorded else "  (no recorded checksum)"))
d2 = listing(dst, db)
print("DONE: copied %d, failed %d | destination now %d objects %.1f GB | every source object present at the destination: %s" % (
    ok, bad, len(d2), sum(o["Size"] for o in d2.values()) / GB, all(k in d2 and d2[k]["Size"] == v["Size"] for k, v in s.items()) if not limit else "n/a (--limit)"))
sys.exit(1 if bad else 0)

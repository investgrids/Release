"""
Local persistent storage for generated media — same /data volume already
used for the SQLite DB and its backups (see app/db/backup.py). Simple file
storage, not object storage: at this scale (a handful of small images a
day) a dedicated bucket service is more infrastructure than the problem
needs; the path is isolated behind `save_image`/`media_path_for` so
swapping to S3-compatible storage later is a one-file change, not a
call-site rewrite.
"""
from __future__ import annotations

from pathlib import Path

_MEDIA_DIR = Path("/data/media")


def save_image(job_id: str, content: bytes, ext: str = "jpg") -> str:
    """Writes the image to disk and returns the public URL path to store on
    the GeneratedMedia row (served by the /api/media/{filename} route).

    Keyed by the job's own ID, not article_id+media_type — a regeneration
    is a *new* job row (see image_worker.regenerate), so it gets a new,
    distinct URL rather than overwriting the old file in place. That makes
    the aggressive immutable Cache-Control on the serving route safe: a URL
    never changes what it points to once issued."""
    # Written under a .tmp name and only renamed onto the real name once
    # fully written — rename is atomic on the same filesystem, so a
    # disk-full or interrupted write can never leave a truncated/corrupt
    # image at the real served path (same pattern as app/db/backup.py's
    # atomic backup writes, same underlying volume).
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{job_id}.{ext}"
    dest = _MEDIA_DIR / filename
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(content)
    tmp.rename(dest)
    return f"/api/media/{filename}"


def read_image(filename: str) -> bytes | None:
    path = _MEDIA_DIR / filename
    # Reject anything that isn't a plain filename in this directory —
    # filenames are server-generated (article_id + media_type), but this
    # is a public GET route, so refuse traversal outright rather than trust
    # the input never contains "..".
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not path.is_file():
        return None
    return path.read_bytes()

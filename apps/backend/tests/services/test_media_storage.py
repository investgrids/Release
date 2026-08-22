"""
app/services/media/storage.py — atomic image writes (2026-08 fix,
companion to the "same image" prompt-builder fix). save_image() used to
write directly to the served filename; a disk-full or interrupted write
could leave a truncated/corrupt file at that exact path, served as a
broken image (user-reported: "sometime the image is broken"). Same
temp-file-then-rename pattern already proven in app/db/backup.py's
atomic backup writes, on the same underlying /data volume.
"""
from __future__ import annotations

import app.services.media.storage as storage_module


def test_save_image_writes_the_real_file_and_returns_its_url(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)
    url = storage_module.save_image("job-abc", b"fake-image-bytes")
    assert url == "/api/media/job-abc.jpg"
    assert (tmp_path / "job-abc.jpg").read_bytes() == b"fake-image-bytes"


def test_save_image_leaves_no_tmp_file_behind_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)
    storage_module.save_image("job-xyz", b"content")
    assert list(tmp_path.glob("*.tmp")) == []


def test_failed_write_never_leaves_a_truncated_file_at_the_real_path(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)

    from pathlib import Path
    real_write_bytes = Path.write_bytes

    def _boom(self, data):
        if self.name.endswith(".tmp"):
            raise OSError("disk full")
        return real_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", _boom)

    try:
        storage_module.save_image("job-fail", b"content")
    except OSError:
        pass

    assert not (tmp_path / "job-fail.jpg").exists()


def test_read_image_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)
    (tmp_path / "real.jpg").write_bytes(b"data")
    assert storage_module.read_image("../real.jpg") is None
    assert storage_module.read_image("..\\real.jpg") is None
    assert storage_module.read_image("sub/real.jpg") is None


def test_read_image_returns_none_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)
    assert storage_module.read_image("nonexistent.jpg") is None


def test_read_image_returns_real_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_module, "_MEDIA_DIR", tmp_path)
    url = storage_module.save_image("job-read", b"real-bytes-here")
    filename = url.rsplit("/", 1)[-1]
    assert storage_module.read_image(filename) == b"real-bytes-here"

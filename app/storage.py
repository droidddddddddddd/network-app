"""Pluggable image storage.

STORAGE_BACKEND = db | s3 | local
  db    (default when ENV=production): bytes in the `media` table, served from /media/<key>. Survives Render's ephemeral disk.
  s3    optional: any S3-compatible bucket (AWS S3, Cloudflare R2). Needs S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY,
        S3_ENDPOINT_URL (R2: https://<account>.r2.cloudflarestorage.com), S3_PUBLIC_BASE_URL and `pip install boto3`.
  local (default in development): files in UPLOAD_DIR served from /uploads/<name>.
"""
import os, uuid
from pathlib import Path

MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", str(2 * 1024 * 1024)))
TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
SIGS = {".png": [b"\x89PNG\r\n\x1a\n"], ".jpg": [b"\xff\xd8\xff"], ".gif": [b"GIF87a", b"GIF89a"], ".webp": [b"RIFF"]}
ROOT = Path(__file__).resolve().parent.parent


def backend() -> str:
    b = os.getenv("STORAGE_BACKEND", "").strip().lower()
    if b in ("db", "s3", "local"): return b
    return "db" if os.getenv("ENV") == "production" else "local"


def upload_dir() -> Path:
    p = Path(os.getenv("UPLOAD_DIR", ROOT / "uploads")); p.mkdir(parents=True, exist_ok=True); return p


def sniff(content_type: str, data: bytes) -> str:
    """Returns the extension if the bytes really are the claimed image type, else raises ValueError."""
    ext = TYPES.get(content_type)
    if not ext: raise ValueError("Only PNG, JPG, GIF or WEBP images.")
    if len(data) > MAX_BYTES: raise ValueError(f"Image too large (max {MAX_BYTES // (1024 * 1024)} MB).")
    if not any(data.startswith(s) for s in SIGS[ext]) or (ext == ".webp" and data[8:12] != b"WEBP"):
        raise ValueError("File content doesn't match an image.")
    return ext


def _s3():
    import boto3  # optional dependency, only needed for STORAGE_BACKEND=s3
    return boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL") or None, region_name=os.getenv("S3_REGION", "auto"),
                        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"), aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"))


def save(db, data: bytes, content_type: str, owner_id=None) -> str:
    from .models import Media
    ext = sniff(content_type, data)
    key = uuid.uuid4().hex + ext
    b = backend()
    if b == "db":
        db.add(Media(key=key, content_type=content_type, size=len(data), data=data, owner_id=owner_id)); db.commit()
        return f"/media/{key}"
    if b == "s3":
        bucket, base = os.getenv("S3_BUCKET"), os.getenv("S3_PUBLIC_BASE_URL", "").rstrip("/")
        if not bucket or not base: raise RuntimeError("S3_BUCKET and S3_PUBLIC_BASE_URL must be set for STORAGE_BACKEND=s3.")
        _s3().put_object(Bucket=bucket, Key=f"uploads/{key}", Body=data, ContentType=content_type, CacheControl="public, max-age=31536000, immutable")
        return f"{base}/uploads/{key}"
    (upload_dir() / key).write_bytes(data)
    return f"/uploads/{key}"


def migrate_local_to_db(db) -> int:
    """Move /uploads/* files that are referenced by users/networks/posts into the media table and rewrite the URLs.
    Idempotent; missing files are left as-is (and reported by count)."""
    from sqlalchemy import select
    from .models import Media, User, Network, Post
    moved, d = 0, upload_dir()
    refs = [(User, "avatar_url"), (Network, "avatar_url"), (Network, "cover_url"), (Post, "image_url")]
    for model, col in refs:
        for obj in db.scalars(select(model).where(getattr(model, col).like("/uploads/%"))):
            name = getattr(obj, col)[len("/uploads/"):]
            f = d / name
            if "/" in name or not f.is_file(): continue
            ext = f.suffix.lower()
            ct = {v: k for k, v in TYPES.items()}.get(ext)
            if not ct: continue
            if not db.scalar(select(Media.id).where(Media.key == name)):
                db.add(Media(key=name, content_type=ct, size=f.stat().st_size, data=f.read_bytes())); db.flush()
            setattr(obj, col, f"/media/{name}"); moved += 1
    db.commit()
    return moved


if __name__ == "__main__":  # python -m app.storage  -> migrate existing local uploads into the database
    from .db import SessionLocal
    with SessionLocal() as s: print(f"migrated {migrate_local_to_db(s)} upload references to database storage")

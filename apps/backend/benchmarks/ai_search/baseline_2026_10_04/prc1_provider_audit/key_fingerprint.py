"""
PRC-1: are the LOCAL and PRODUCTION provider keys the same keys (same account, therefore shared quota)? Prints, per provider, only a truncated SHA-256 fingerprint (8 hex characters)
of the configured key, which cannot be reversed to the key, or "not configured". Never prints a key or any part of one.

Run locally and via `railway run`, then compare the two lines per provider.
"""
import hashlib
import sys

sys.path.insert(0, ".")
from app.core.config import settings  # noqa: E402

for name in ("groq_api_key", "openrouter_api_key", "gemini_api_key"):
    v = getattr(settings, name, None)
    print(f"{name:20} fingerprint: {hashlib.sha256(v.encode()).hexdigest()[:8] if v else 'not configured'}")

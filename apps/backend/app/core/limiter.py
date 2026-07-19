"""
Shared slowapi Limiter instance.

Lives outside main.py so route modules can import it for per-endpoint
@limiter.limit(...) overrides without a circular import (main.py imports
every app.api.* router module, so those modules can't import back from
app.main).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])

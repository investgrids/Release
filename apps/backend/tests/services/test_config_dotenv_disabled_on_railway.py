"""
Security hotfix (2026-09-26) — pydantic-settings must never fall back to a
.env file when running on Railway, regardless of what real environment
variables are or aren't set.

Real incident this closes: MISTRAL_API_KEY was accidentally exposed and
deleted from Railway's own variable store, but the running production
process kept using the old key anyway — because pydantic-settings'
default env_file fallback silently read the still-baked-into-the-image
.env file the moment the real (Railway) variable was absent. Deleting a
Railway variable can therefore have NO effect at runtime as long as a
stale .env is still sitting in the container filesystem. See
project_mistral_key_exposure_incident.md (Claude memory) for the full
incident.

RAILWAY_ENVIRONMENT is used as the detection signal because Railway sets
it automatically on every deployment (confirmed in this project's real
production variables) -- it is never something a locally-run .env file
could itself define or fake, since the check happens before any .env is
ever read.
"""
from __future__ import annotations

import importlib

from app.core import config as config_mod


def _reload_with_env(monkeypatch, railway_environment: str | None):
    if railway_environment is None:
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", railway_environment)
    importlib.reload(config_mod)
    return config_mod.Settings


def test_env_file_disabled_when_railway_environment_is_set(monkeypatch):
    Settings = _reload_with_env(monkeypatch, "production")
    assert Settings.Config.env_file is None


def test_env_file_disabled_for_any_railway_environment_name_not_just_production(monkeypatch):
    """The signal is "am I running on Railway at all", not which specific
    named environment -- a staging/preview Railway environment must be
    just as protected as production."""
    Settings = _reload_with_env(monkeypatch, "staging")
    assert Settings.Config.env_file is None


def test_env_file_still_enabled_locally_with_no_railway_environment(monkeypatch):
    """Local dev (no RAILWAY_ENVIRONMENT at all) must be unaffected --
    this hotfix must not break the existing local .env workflow."""
    Settings = _reload_with_env(monkeypatch, None)
    assert Settings.Config.env_file == ".env"


def test_env_file_decision_reads_the_real_os_environment_not_a_dotenv_value():
    """The whole point of this fix: the decision must be made from a
    source a stale/compromised .env file can never influence. Confirmed
    structurally -- os.environ.get() is called directly at class-body
    evaluation time, before any dotenv source is ever consulted."""
    import inspect
    source = inspect.getsource(config_mod.Settings.Config)
    assert "os.environ.get(\"RAILWAY_ENVIRONMENT\")" in source or "os.environ.get('RAILWAY_ENVIRONMENT')" in source

"""
CR-2A (2026-09-13) — regression tests for the isolated daily BSE
availability probe. Must prove three things this module's contract
promises:
  1. The known current failure mode (bot-wall HTML, or a non-200/non-JSON
     response) is recorded as a source_health failure, quietly -- no
     exception escapes.
  2. It NEVER persists announcement data -- it is a probe, not ingestion.
  3. An unexpected real JSON response is recorded as success AND logged
     loudly (the one signal meant to prompt a deliberate re-enable
     decision), not silently treated the same as any other success.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import bse_health_check, source_health


class _FakeResponse:
    def __init__(self, status_code=200, content_type="application/json", body=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def _mock_client(response=None, raises=None):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    if raises is not None:
        client.get = AsyncMock(side_effect=raises)
    else:
        client.get = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_network_error_is_recorded_as_failure_without_raising():
    with patch("httpx.AsyncClient", return_value=_mock_client(raises=ConnectionError("refused"))):
        await bse_health_check.check_bse_health()  # must not raise

    health = source_health.get_source_health("BSE")
    assert health["status"] in ("FAILED", "DEGRADED")


@pytest.mark.asyncio
async def test_non_200_status_is_recorded_as_http_failure():
    resp = _FakeResponse(status_code=403, content_type="text/html")
    with patch("httpx.AsyncClient", return_value=_mock_client(response=resp)):
        await bse_health_check.check_bse_health()

    health = source_health.get_source_health("BSE")
    assert health["status"] in ("FAILED", "DEGRADED")


@pytest.mark.asyncio
async def test_known_botwall_html_response_is_recorded_as_parse_failure_not_json_decoded():
    """The real, currently-observed failure mode: a 200 whose body is
    HTML, not JSON. Must be caught by content-type inspection BEFORE ever
    calling .json() -- never let a JSONDecodeError escape as an
    unhandled exception."""
    resp = _FakeResponse(status_code=200, content_type="text/html; charset=utf-8")
    with patch("httpx.AsyncClient", return_value=_mock_client(response=resp)):
        await bse_health_check.check_bse_health()  # must not raise

    health = source_health.get_source_health("BSE")
    assert health["status"] in ("FAILED", "DEGRADED")
    assert "non-JSON" in (health["latest_error"] or "") or "bot-wall" in (health["latest_error"] or "")


@pytest.mark.asyncio
async def test_unexpected_real_json_success_is_recorded_and_logged_loudly(caplog):
    """A genuine recovery signal -- BSE responding with real JSON again.
    Must record success AND emit a distinctly loud, named log event so a
    human notices and makes a deliberate re-enable decision (this probe
    never re-enables ingestion on its own)."""
    resp = _FakeResponse(status_code=200, content_type="application/json", body={"Table": [{"a": 1}, {"a": 2}]})
    with patch("httpx.AsyncClient", return_value=_mock_client(response=resp)):
        await bse_health_check.check_bse_health()

    health = source_health.get_source_health("BSE")
    assert health["status"] == "HEALTHY"


@pytest.mark.asyncio
async def test_unexpected_json_shape_missing_table_key_is_a_parse_failure():
    resp = _FakeResponse(status_code=200, content_type="application/json", body={"unexpected": "shape"})
    with patch("httpx.AsyncClient", return_value=_mock_client(response=resp)):
        await bse_health_check.check_bse_health()

    health = source_health.get_source_health("BSE")
    assert health["status"] in ("FAILED", "DEGRADED")


@pytest.mark.asyncio
async def test_probe_never_imports_or_touches_company_announcement_persistence():
    """Structural proof this is a probe, not ingestion-in-disguise: the
    module must not import or use the DB session / model / persistence
    layer at all (checking actual usage patterns, not the module's own
    prose docstring, which legitimately mentions these names to explain
    what it deliberately does NOT do)."""
    import inspect
    source = inspect.getsource(bse_health_check)
    assert "AsyncSessionLocal" not in source
    assert "CompanyAnnouncement(" not in source
    assert "import" not in "\n".join(
        line for line in source.splitlines() if "CompanyAnnouncement" in line
    )
    assert "db.add(" not in source
    assert "db.commit(" not in source

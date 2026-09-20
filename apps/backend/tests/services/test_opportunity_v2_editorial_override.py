"""
app/api/admin.py's opportunity-v2-editorial-override/-clear endpoints
(2026-09-20) -- a canary/editorial safety valve letting a human-reviewed,
strictly-evidence-traceable title/summary take precedence over the
generated ones without ever overwriting or discarding
current_title/current_summary. Real DB-backed tests covering: admin-key
authorization, exact-ID targeting, stale-generated-hash rejection,
shadow-only enforcement, preserved generated content, read-service
precedence (_effective_title/_effective_summary), idempotency, and
clear-for-rollback.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.core.config import settings
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.read_service import _effective_summary, _effective_title

client = TestClient(app)
HEADERS = {"X-Admin-Key": settings.admin_api_key} if getattr(settings, "admin_api_key", None) else {}


def _generated_hash(title: str, summary: str) -> str:
    return hashlib.sha256(f"{title}\n{summary}".encode("utf-8")).hexdigest()


def _make_opp(*, public_status: str = "shadow") -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:edtest", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title="Generated Test Title", formation_score=50.0, formation_at=now,
        current_title="Generated Test Title", current_summary="Generated overreaching summary.", current_score=50.0,
        sectors=[], companies=[], contradictions=[],
        slug=f"real-editorial-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _cleanup(ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(ids)))
        await db.commit()


def _override_body(opp: OpportunityV2, **overrides) -> dict:
    base = {
        "title": "Strictly Factual Title",
        "summary": "Strictly factual summary tied to displayed evidence.",
        "reason": "narrative overreach removed per editorial review",
        "expected_generated_hash": _generated_hash(opp.current_title, opp.current_summary),
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_no_admin_key_is_rejected():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp),
        )  # no HEADERS
        assert resp.status_code in (401, 403)

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.editorial_title is None, "an unauthorized request must not mutate anything"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_override_targets_exactly_the_given_id_never_a_second_row():
    target = _make_opp()
    bystander = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(target)
        db.add(bystander)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={target.id}",
            json=_override_body(target), headers=HEADERS,
        )
        assert resp.status_code == 200

        async with AsyncSessionLocal() as db:
            refreshed_target = await db.get(OpportunityV2, target.id)
            refreshed_bystander = await db.get(OpportunityV2, bystander.id)
        assert refreshed_target.editorial_title == "Strictly Factual Title"
        assert refreshed_bystander.editorial_title is None, "override must never touch an unrelated row"
    finally:
        await _cleanup([target.id, bystander.id])


@pytest.mark.asyncio
async def test_stale_generated_hash_is_rejected_and_row_untouched():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp, expected_generated_hash="0" * 64),
            headers=HEADERS,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason"] == "stale_generated_hash"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.editorial_title is None
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_shadow_only_enforcement_rejects_a_public_row():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp), headers=HEADERS,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason"] == "not_shadow"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.editorial_title is None
        assert refreshed.public_status == "public", "the endpoint must never itself change public_status"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_missing_reason_is_rejected():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp, reason="   "), headers=HEADERS,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason"] == "reason_required"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_generated_content_is_preserved_never_overwritten():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp), headers=HEADERS,
        )
        assert resp.status_code == 200

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.current_title == "Generated Test Title"
        assert refreshed.current_summary == "Generated overreaching summary."
        assert refreshed.editorial_title == "Strictly Factual Title"
        assert refreshed.editorial_summary == "Strictly factual summary tied to displayed evidence."
        assert refreshed.editorial_reason == "narrative overreach removed per editorial review"
        assert refreshed.editorial_updated_at is not None
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_read_service_precedence_prefers_editorial_over_generated():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        # Before override: effective values equal the generated ones.
        async with AsyncSessionLocal() as db:
            before = await db.get(OpportunityV2, opp.id)
        assert _effective_title(before) == "Generated Test Title"
        assert _effective_summary(before) == "Generated overreaching summary."

        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp), headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["effective_title"] == "Strictly Factual Title"
        assert resp.json()["effective_summary"] == "Strictly factual summary tied to displayed evidence."

        async with AsyncSessionLocal() as db:
            after = await db.get(OpportunityV2, opp.id)
        assert _effective_title(after) == "Strictly Factual Title"
        assert _effective_summary(after) == "Strictly factual summary tied to displayed evidence."
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_repeated_identical_override_call_is_idempotent():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        body = _override_body(opp)
        resp1 = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=body, headers=HEADERS,
        )
        assert resp1.status_code == 200

        # expected_generated_hash still matches -- current_title/current_summary
        # (the GENERATED content) never changed, only editorial_* did.
        resp2 = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=body, headers=HEADERS,
        )
        assert resp2.status_code == 200
        assert resp2.json()["effective_title"] == resp1.json()["effective_title"]
        assert resp2.json()["effective_summary"] == resp1.json()["effective_summary"]
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_clear_restores_generated_content_as_effective_and_is_idempotent():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        set_resp = client.post(
            f"/api/admin/opportunity-v2-editorial-override?opportunity_id={opp.id}",
            json=_override_body(opp), headers=HEADERS,
        )
        assert set_resp.status_code == 200

        async with AsyncSessionLocal() as db:
            row = await db.get(OpportunityV2, opp.id)
        clear_body = {
            "reason": "rollback per review",
            "expected_generated_hash": _generated_hash(row.current_title, row.current_summary),
        }
        clear_resp = client.post(
            f"/api/admin/opportunity-v2-editorial-clear?opportunity_id={opp.id}",
            json=clear_body, headers=HEADERS,
        )
        assert clear_resp.status_code == 200
        assert clear_resp.json()["effective_title"] == "Generated Test Title"
        assert clear_resp.json()["effective_summary"] == "Generated overreaching summary."

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.editorial_title is None
        assert refreshed.editorial_summary is None
        assert refreshed.editorial_reason is None
        assert refreshed.editorial_updated_at is None
        assert refreshed.current_title == "Generated Test Title", "clearing must never touch generated content"

        # Idempotent: clearing an already-cleared row succeeds as a no-op.
        clear_resp2 = client.post(
            f"/api/admin/opportunity-v2-editorial-clear?opportunity_id={opp.id}",
            json=clear_body, headers=HEADERS,
        )
        assert clear_resp2.status_code == 200
        assert clear_resp2.json()["editorial_title"] is None
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_clear_is_also_shadow_only_and_uses_the_same_stale_hash_guard():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(
            f"/api/admin/opportunity-v2-editorial-clear?opportunity_id={opp.id}",
            json={"reason": "x", "expected_generated_hash": _generated_hash(opp.current_title, opp.current_summary)},
            headers=HEADERS,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason"] == "not_shadow"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_unknown_id_returns_not_found():
    resp = client.post(
        "/api/admin/opportunity-v2-editorial-override?opportunity_id=this-id-does-not-exist",
        json={
            "title": "x", "summary": "y", "reason": "z",
            "expected_generated_hash": "0" * 64,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 404

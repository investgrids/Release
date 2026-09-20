"""
app/api/admin.py's temporary opportunity-v2-canary-promote/-revert
endpoints (2026-09-20) -- real DB-backed tests for the exact-row-guard
contract: an update must affect precisely one row matching BOTH the id
AND the expected current public_status, or it must roll back and report
failure rather than silently doing nothing or affecting the wrong row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.core.config import settings
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal

client = TestClient(app)
HEADERS = {"X-Admin-Key": settings.admin_api_key} if getattr(settings, "admin_api_key", None) else {}


def _make_opp(*, public_status: str) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:canarytest", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title="Real Canary Test Opportunity", formation_score=60.0, formation_at=now,
        current_title="Real Canary Test Opportunity", current_summary="Real test summary.", current_score=60.0,
        sectors=["Banking"], companies=[], contradictions=[],
        slug=f"real-canary-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _cleanup(ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_promote_affects_exactly_one_shadow_row_and_flips_it_to_public():
    opp = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["public_status"] == "public"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "public"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_refuses_a_row_that_is_already_public_never_a_silent_noop():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 409

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "public"  # unchanged
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_refuses_an_unknown_id():
    resp = client.post("/api/admin/opportunity-v2-canary-promote?opportunity_id=this-id-does-not-exist", headers=HEADERS)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revert_affects_exactly_one_public_row_and_flips_it_back_to_shadow():
    opp = _make_opp(public_status="public")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-revert?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["public_status"] == "shadow"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_revert_refuses_a_row_that_is_already_shadow():
    opp = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-revert?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 409

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"  # unchanged
    finally:
        await _cleanup([opp.id])


@pytest.mark.asyncio
async def test_promote_never_affects_a_second_unrelated_row():
    target = _make_opp(public_status="shadow")
    bystander = _make_opp(public_status="shadow")
    async with AsyncSessionLocal() as db:
        db.add(target)
        db.add(bystander)
        await db.commit()
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={target.id}", headers=HEADERS)
        assert resp.status_code == 200

        async with AsyncSessionLocal() as db:
            refreshed_target = await db.get(OpportunityV2, target.id)
            refreshed_bystander = await db.get(OpportunityV2, bystander.id)
        assert refreshed_target.public_status == "public"
        assert refreshed_bystander.public_status == "shadow"  # untouched
    finally:
        await _cleanup([target.id, bystander.id])


# ── Item 7 enforcement: the promotion-eligibility gate, exercised through
# the real HTTP endpoint (not just the pure gate function directly) --
# proves the gate is actually wired into the one real write path. ──────────

import ast  # noqa: E402
from pathlib import Path  # noqa: E402

from app.db.models.development import Development, DevelopmentEvidence  # noqa: E402


def _make_dev(title: str) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=None, companies=[], sectors=[], themes=[],
        first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=0.8,
        evidence_count=1, schema_version="test",
    )


async def _seed_with_dev(opp: OpportunityV2, dev: Development) -> None:
    now = datetime.now(timezone.utc)
    from app.db.models.opportunity_v2 import OpportunityV2Development
    async with AsyncSessionLocal() as db:
        db.add(opp)
        db.add(dev)
        await db.commit()
        db.add(OpportunityV2Development(opportunity_id=opp.id, development_id=dev.id, added_at=now))
        await db.commit()


async def _cleanup_with_dev(opp_id: str, dev_id: str) -> None:
    from app.db.models.opportunity_v2 import OpportunityV2Development
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpportunityV2Development).where(OpportunityV2Development.opportunity_id == opp_id))
        await db.execute(delete(OpportunityV2).where(OpportunityV2.id == opp_id))
        await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id == dev_id))
        await db.execute(delete(Development).where(Development.id == dev_id))
        await db.commit()


@pytest.mark.asyncio
async def test_promote_endpoint_rejects_a_routine_only_opportunity_with_the_exact_reason():
    opp = _make_opp(public_status="shadow")
    dev = _make_dev("Real Co Ltd has submitted the Exchange a copy Srutinizers report of Postal Ballot.")
    await _seed_with_dev(opp, dev)
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 422
        body = resp.json()["detail"]
        assert body["reason"] == "routine_filing_only"
        assert len(body["evaluated"]) == 1

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"  # provably untouched by the rejected attempt
    finally:
        await _cleanup_with_dev(opp.id, dev.id)


@pytest.mark.asyncio
async def test_promote_endpoint_rejects_a_synthetic_exposure_development_with_the_exact_reason():
    opp = _make_opp(public_status="shadow")
    dev = _make_dev("Directly exposed to Energy opportunity through core operations.")
    await _seed_with_dev(opp, dev)
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason"] == "synthetic_exposure_development"

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"
    finally:
        await _cleanup_with_dev(opp.id, dev.id)


@pytest.mark.asyncio
async def test_promote_endpoint_accepts_a_genuinely_material_opportunity():
    opp = _make_opp(public_status="shadow")
    dev = _make_dev("Reliance announces $2B acquisition of renewable energy assets")
    await _seed_with_dev(opp, dev)
    try:
        resp = client.post(f"/api/admin/opportunity-v2-canary-promote?opportunity_id={opp.id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["public_status"] == "public"
    finally:
        await _cleanup_with_dev(opp.id, dev.id)


def _find_public_status_public_writes(tree: "ast.AST") -> list[int]:
    """AST-level scan for a real write of public_status to the literal
    "public" -- a keyword arg (e.g. .values(public_status="public") or a
    constructor call) or an attribute/subscript assignment. Deliberately
    ignores comments, docstrings, and equality comparisons (== "public"),
    which the earlier regex-based draft of this guard falsely flagged."""
    hits: list[int] = []

    def is_public_literal(node: "ast.AST") -> bool:
        return isinstance(node, ast.Constant) and node.value == "public"

    def targets_public_status(node: "ast.AST") -> bool:
        return isinstance(node, ast.Attribute) and node.attr == "public_status"

    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "public_status" and is_public_literal(node.value):
            hits.append(node.lineno)
        elif isinstance(node, ast.Assign):
            if is_public_literal(node.value):
                for t in node.targets:
                    if targets_public_status(t) or (isinstance(t, ast.Name) and t.id == "public_status"):
                        hits.append(node.lineno)
    return hits


def test_no_code_path_writes_public_status_public_outside_the_gated_endpoint():
    """Durable regression guard for 'direct service invocation cannot
    bypass the gate' -- a full grep audit (2026-09-20) confirmed
    app/api/admin.py's promote endpoint is the ONE real write path to
    public_status="public" in this codebase (orchestration.py only ever
    sets "shadow" at creation). This makes that invariant an automated
    check: fails if ANY other .py file under app/ ever assigns
    public_status to the literal "public" directly, which would bypass
    evaluate_promotion_eligibility()'s gate entirely. Uses real AST
    parsing (not text/regex matching) so comments, docstrings, and
    `== "public"` read-filters -- all real and expected elsewhere in this
    codebase -- can never trip it."""
    app_dir = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "admin.py" and py_file.parent.name == "api":
            continue  # the one authorized, gated write path
        tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        hits = _find_public_status_public_writes(tree)
        if hits:
            offenders.append(f"{py_file.relative_to(app_dir)}:{hits}")
    assert offenders == [], (
        f"Found a public_status='public' write outside the gated promote endpoint: {offenders}. "
        "This would bypass evaluate_promotion_eligibility() -- route it through app/api/admin.py's "
        "opportunity_v2_canary_promote instead."
    )

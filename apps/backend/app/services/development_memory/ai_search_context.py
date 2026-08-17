"""
Development Memory -> AI Search context — Phase 6F.

One shared builder, called from both AI Search V2 (ai_search_service.py)
and V3 (ai_search/evidence.py) — NOT a third pipeline, no routing
changes. Per the explicit 6F scope decision: do not build a separate
Brain implementation inside each pipeline; both call this one function,
so when V2/V3 eventually get unified (a separate, later, much larger
initiative — "6G"), this piece survives the merge untouched.

Mirrors the exact existing "single-company lookup, inject only if
present, fail silently" pattern already used 12 times across both
pipelines for Intelligence Graph company context, valuation, VIX, etc.
(see the Company Research block in both files, immediately preceding
where this gets called) — same gating shape, same truncation/top-N
discipline (title/evidence capped like the existing story_text[:220]
precedent, evidence/analogues capped to a small top-N like the existing
[:3]/[:5] blocks elsewhere), same try/except-and-return-None-on-any-
failure contract.

Only surfaces a Development that's already graph-worthy (reuses
is_graph_worthy() — the same "does this matter" gate used for graph
nodes and, more strictly, for shadow predictions) — a single stray
low-value evidence row must not show up as "Development Memory" in a
user-facing answer.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.services.development_memory.graph_link import is_graph_worthy
from app.services.development_memory.historical_retrieval import find_similar_developments_context
from app.services.development_memory.reconciliation import reconcile_development

MAX_EVIDENCE_LINES = 3
MAX_ANALOGUE_LINES = 2


async def _find_relevant_development(db: AsyncSession, symbol: str) -> Development | None:
    candidates = (await db.execute(
        select(Development)
        .where(Development.primary_company == symbol)
        .order_by(Development.last_observed_at.desc())
        .limit(5)
    )).scalars().all()
    for dev in candidates:
        if await is_graph_worthy(db, dev):
            return dev
    return None


def _format_evidence_line(item) -> str:
    title = (item.title or item.source_type)[:100]
    return f"• {title} — {item.direction}"


def _format_analogue_line(analogue: dict) -> str:
    title = (analogue.get("event_title") or "")[:100]
    similarity = analogue.get("similarity")
    outcome = analogue.get("nifty_1w")
    outcome_str = f"{outcome:+.1f}%" if isinstance(outcome, (int, float)) else "n/a"
    sim_str = f"{similarity:.0f}%" if isinstance(similarity, (int, float)) else "n/a"
    return f"• {title} — similarity {sim_str} · 1W outcome: {outcome_str}"


async def build_development_context(db: AsyncSession, symbol: str) -> str | None:
    """Returns a compact text block for `symbol`'s most relevant
    Development, or None if there isn't one worth surfacing (no
    graph-worthy Development exists, or any lookup fails). Callers
    inject the result exactly like every other optional context block
    in both pipelines — no special handling needed."""
    try:
        dev = await _find_relevant_development(db, symbol)
        if dev is None:
            return None

        reconciliation = await reconcile_development(db, dev)
        historical = await find_similar_developments_context(dev)

        lines = ["DEVELOPMENT MEMORY (real, from Market Ripple's Intelligence Brain)", ""]
        lines.append(f"Development: {dev.canonical_title[:150]}")

        confidence_pct = round((dev.current_confidence or 0.0) * 100)
        lines.append(f"Reconciliation: {reconciliation.conflict_bucket} (confidence: {confidence_pct}%)")

        combined_evidence = sorted(
            reconciliation.positive_evidence + reconciliation.negative_evidence,
            key=lambda e: e.observed_at or "", reverse=True,
        )[:MAX_EVIDENCE_LINES]
        if combined_evidence:
            lines.append("Evidence:")
            lines.extend(_format_evidence_line(e) for e in combined_evidence)

        if historical.analogues:
            lines.append("Historical analogues:")
            lines.extend(_format_analogue_line(a) for a in historical.analogues[:MAX_ANALOGUE_LINES])

        return "\n".join(lines)
    except Exception:
        return None

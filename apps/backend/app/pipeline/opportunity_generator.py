"""
Opportunity Generator — full AI pipeline.

Flow:
  Incoming events
    → classify
    → group by sector/theme
    → generate opportunity (AI or heuristic)
    → score
    → generate timeline, graph, companies
    → store in PostgreSQL via repository
"""
from __future__ import annotations

import hashlib
import json
import structlog
import re
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.opportunity import Opportunity
from app.pipeline.classifier import classify_text, classify_with_ai
from app.repositories.opportunity_repository import OpportunityRepository

logger = structlog.get_logger(__name__)

# ── Sector colour palette ─────────────────────────────────────────────────────

_SECTOR_COLORS: dict[str, str] = {
    "Infrastructure": "#6366f1",
    "Technology":     "#0ea5e9",
    "Energy":         "#f59e0b",
    "Banking":        "#10b981",
    "Railways":       "#8b5cf6",
    "Defence":        "#ef4444",
    "Manufacturing":  "#f97316",
    "Pharma":         "#14b8a6",
    "Automotive":     "#3b82f6",
    "FMCG":           "#84cc16",
    "Metals":         "#6b7280",
    "Real Estate":    "#ec4899",
}

# ── Company metadata ──────────────────────────────────────────────────────────

_COMPANY_META: dict[str, dict] = {
    "NTPC":       {"name": "NTPC",                "sector": "Energy"},
    "RVNL":       {"name": "Rail Vikas Nigam",    "sector": "Railways"},
    "IRCON":      {"name": "Ircon International", "sector": "Railways"},
    "LT":         {"name": "Larsen & Toubro",     "sector": "Infrastructure"},
    "BEL":        {"name": "Bharat Electronics",  "sector": "Defence"},
    "HAL":        {"name": "HAL",                 "sector": "Defence"},
    "RELIANCE":   {"name": "Reliance Industries", "sector": "Energy"},
    "TCS":        {"name": "TCS",                 "sector": "Technology"},
    "HDFCBANK":   {"name": "HDFC Bank",           "sector": "Banking"},
    "INFY":       {"name": "Infosys",             "sector": "Technology"},
    "TATASTEEL":  {"name": "Tata Steel",          "sector": "Metals"},
    "TATAMOTORS": {"name": "Tata Motors",         "sector": "Automotive"},
    "ADANIENT":   {"name": "Adani Enterprises",   "sector": "Infrastructure"},
    "BEML":       {"name": "BEML",                "sector": "Railways"},
    "SBIN":       {"name": "SBI",                 "sector": "Banking"},
    "ICICIBANK":  {"name": "ICICI Bank",          "sector": "Banking"},
    "BAJFINANCE": {"name": "Bajaj Finance",       "sector": "Banking"},
    "MARUTI":     {"name": "Maruti Suzuki",       "sector": "Automotive"},
    "SUNPHARMA":  {"name": "Sun Pharma",          "sector": "Pharma"},
    "AIRTEL":     {"name": "Bharti Airtel",       "sector": "Technology"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(title: str, suffix: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:160]
    if suffix:
        base = f"{base}-{suffix}"
    return base[:180]


def _score_opportunity(events: list[dict], companies: list[str], sectors: list[str]) -> float:
    base = 60.0
    base += min(20, len(events) * 3)
    base += min(10, len(companies) * 1.5)
    base += min(10, len(sectors) * 2)
    return round(min(99, base), 1)


def _build_heuristic_summary(title: str, sectors: list[str], companies: list[str]) -> dict:
    sector_str = " and ".join(sectors[:2]) if sectors else "multiple sectors"
    company_str = ", ".join(companies[:3]) if companies else "key listed companies"
    return {
        "matters": f"This opportunity in {sector_str} is driven by policy and market dynamics that create sustained multi-year investment cycles.",
        "benefits": f"Companies like {company_str} stand to benefit directly through order inflows and revenue growth.",
        "risks": [
            "Execution delays",
            "Policy changes or budget reallocation",
            "Global macro headwinds",
        ],
        "invalidate": "Significant slowdown in government spending or adverse regulatory changes could delay the opportunity.",
        "why_bullets": [
            f"Strong government focus on {sector_str}",
            "Multi-year investment cycle with visible order pipeline",
            f"Key beneficiaries: {company_str}",
            "Supported by budget allocations and policy frameworks",
        ],
    }


async def _call_ai(prompt: str, max_tokens: int = 600) -> str | None:
    if not settings.deepseek_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("AI call failed: %s", exc)
        return None


def _parse_json_block(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


# ── Core pipeline ─────────────────────────────────────────────────────────────

async def generate_opportunity_from_events(
    db: AsyncSession,
    event_texts: list[dict],
    source: str = "pipeline",
) -> Opportunity | None:
    """
    event_texts: list of {id, title, summary, published_at, category}
    source: "pipeline" for real news-driven generation (default), "seed" for
        the static placeholder opportunities inserted on first empty-DB boot
        — kept distinguishable forever via Opportunity.source.

    Returns the created/updated Opportunity ORM object, or None on failure.
    """
    if not event_texts:
        return None

    repo = OpportunityRepository(db)

    # 1. Classify all events, collect sectors + companies
    all_sectors: list[str] = []
    all_companies: list[str] = []
    for ev in event_texts:
        text = f"{ev.get('title','')} {ev.get('summary','')}"
        classification = await classify_with_ai(text)
        all_sectors.extend(classification.get("sectors", []))
        all_companies.extend(classification.get("companies", []))

    # Deduplicate, preserve order
    seen: set[str] = set()
    sectors = [s for s in all_sectors if not (s in seen or seen.add(s))][:4]  # type: ignore[func-returns-value]
    seen.clear()
    companies = [c for c in all_companies if not (c in seen or seen.add(c))][:8]  # type: ignore[func-returns-value]

    combined_text = " ".join(
        f"{e.get('title','')} {e.get('summary','')}" for e in event_texts[:5]
    )

    # 2. Generate opportunity title + summary via AI
    title = ""
    summary = ""
    ai_summary_data: dict = {}

    ai_prompt = f"""You are an Indian equity market analyst.
Based on these recent events, identify ONE investment opportunity theme.
Return ONLY valid JSON — no markdown, no explanation.

EVENTS:
{combined_text[:1500]}

SECTORS DETECTED: {sectors}
COMPANIES DETECTED: {companies}

Return:
{{
  "title": "<short opportunity title, 3-6 words>",
  "summary": "<2-3 sentence summary of why this is an opportunity>",
  "trend": "<Strongly Positive|Positive|Neutral|Negative>",
  "risk_level": "<Low|Medium|High>",
  "time_horizon": "<1-3 Years|3-5 Years|5-7 Years>",
  "matters": "<why this matters for investors>",
  "benefits": "<who benefits and how>",
  "risks": ["<risk1>", "<risk2>", "<risk3>"],
  "invalidate": "<what could invalidate this>",
  "why_bullets": ["<bullet1>", "<bullet2>", "<bullet3>", "<bullet4>"]
}}"""

    ai_text = await _call_ai(ai_prompt, max_tokens=700)
    if ai_text:
        parsed = _parse_json_block(ai_text)
        if parsed:
            title = parsed.get("title", "")
            summary = parsed.get("summary", "")
            ai_summary_data = {
                "matters":     parsed.get("matters", ""),
                "benefits":    parsed.get("benefits", ""),
                "risks":       parsed.get("risks", []),
                "invalidate":  parsed.get("invalidate", ""),
                "why_bullets": parsed.get("why_bullets", []),
            }
            trend = parsed.get("trend", "Positive")
            risk = parsed.get("risk_level", "Medium")
            horizon = parsed.get("time_horizon", "3-5 Years")

    # Heuristic fallbacks
    if not title:
        # Extract specific theme from the actual event articles
        first_ev = event_texts[0] if event_texts else {}
        ev_title = first_ev.get("title", "")
        sector_str = sectors[0] if sectors else "Market"
        if ev_title and len(ev_title) > 10:
            # Use key words from actual event (truncated to ~50 chars)
            words = ev_title.split()[:8]
            title = " ".join(words) if len(" ".join(words)) > 15 else f"{sector_str} Growth Opportunity"
        else:
            title = f"{sector_str} Growth Opportunity"
    if not summary:
        # Build from actual event content
        ev_titles = [ev.get("title", "") for ev in event_texts[:3] if ev.get("title")]
        if ev_titles:
            summary = f"Investment opportunity driven by: {'; '.join(ev_titles[:2])}. Key sectors: {', '.join(sectors[:2])}."
        else:
            summary = f"Emerging opportunity in {', '.join(sectors[:2])} backed by recent policy and market developments."
    if not ai_summary_data:
        ai_summary_data = _build_heuristic_summary(title, sectors, companies)
    if "trend" not in locals():
        trend = "Positive"
    if "risk" not in locals():
        risk = "Medium"
    if "horizon" not in locals():
        horizon = "3 – 5 Years"

    score = _score_opportunity(event_texts, companies, sectors)
    confidence = min(0.95, score / 110)
    # Include a short hash of event IDs so different event groups with the same
    # AI-generated title don't collide on slug (common when heuristic kicks in).
    event_hash = hashlib.md5(
        "".join(sorted(ev.get("id", "") for ev in event_texts)).encode()
    ).hexdigest()[:6]
    slug = _slug(title, suffix=event_hash)

    # 3. Upsert opportunity
    opp = await repo.upsert_opportunity({
        "slug": slug,
        "title": title,
        "summary": summary,
        "opportunity_score": score,
        "confidence": round(confidence, 2),
        "trend": trend,
        "risk_level": risk,
        "time_horizon": horizon,
        "sectors": sectors,
        "ai_summary": ai_summary_data,
        "source": source,
    })

    # 4. Metrics (heuristic)
    await repo.replace_metrics(opp.id, {
        "revenue_potential": f"₹{round(score * 0.3, 1)} – {round(score * 0.5, 1)} Lakh Cr",
        "expected_cagr": f"{round(score * 0.18, 0):.0f}% – {round(score * 0.25, 0):.0f}% CAGR",
        "eps_growth": f"{round(score * 0.2, 0):.0f}% – {round(score * 0.28, 0):.0f}% CAGR",
        "investment_cycle": "Multi-year",
        "market_size": f"{round(score * 0.2, 0):.0f}%+ CAGR",
    })

    # 5. Timeline (4 phases)
    await repo.replace_timeline(opp.id, [
        {"order": 0, "phase": "Policy & Announcement", "date_label": "0 – 6 Months", "title": "Initial Phase",  "description": "Policy approvals & early investments",  "status": "done"   },
        {"order": 1, "phase": "Capex Ramp-up",          "date_label": "6 – 18 Months","title": "Growth Phase",   "description": "Project execution & procurement surge", "status": "active" },
        {"order": 2, "phase": "Execution",               "date_label": "18 – 36 Months","title": "Scale Phase",  "description": "Capacity expansion & adoption scale",   "status": "pending"},
        {"order": 3, "phase": "Maturity",                "date_label": "3 – 5 Years",  "title": "Revenue Phase", "description": "Revenue realisation & strong cash flows","status": "pending"},
    ])

    # 6. Beneficiary companies
    company_rows = []
    for i, sym in enumerate(companies[:8]):
        meta = _COMPANY_META.get(sym, {"name": sym, "sector": sectors[0] if sectors else ""})
        base_score = max(70, score - i * 2)
        company_rows.append({
            "company_id":   sym,
            "company_name": meta["name"],
            "impact_score": round(base_score, 1),
            "impact_label": "Very High" if base_score >= 90 else "High" if base_score >= 80 else "Medium",
            "trend":        "up",
            "confidence":   round(confidence - i * 0.02, 2),
            "reason":       f"Directly exposed to {sectors[0] if sectors else 'this'} opportunity through core operations.",
        })
    await repo.replace_companies(opp.id, company_rows)

    # 7. Sector distribution
    total_sectors = len(sectors) or 1
    sector_rows = []
    remaining = 100
    for idx, sec in enumerate(sectors):
        pct = round(remaining / (total_sectors - idx)) if idx < total_sectors - 1 else remaining
        sector_rows.append({
            "sector":     sec,
            "percentage": pct,
            "color":      _SECTOR_COLORS.get(sec, "#6366f1"),
        })
        remaining -= pct
    await repo.replace_sector_distribution(opp.id, sector_rows)

    # 8. Graph nodes + edges
    nodes = [{"node_id": "opp", "label": title, "node_type": "opportunity", "node_metadata": {}}]
    edges = []
    for sec in sectors:
        nid = f"sec_{sec.lower()[:8]}"
        nodes.append({"node_id": nid, "label": sec, "node_type": "sector", "node_metadata": {}})
        edges.append({"source": "opp", "target": nid, "edge_relationship": "drives"})
    for sym in companies[:5]:
        meta = _COMPANY_META.get(sym, {"name": sym})
        nid = f"co_{sym.lower()}"
        nodes.append({"node_id": nid, "label": meta["name"], "node_type": "company", "node_metadata": {}})
        edges.append({"source": "opp", "target": nid, "edge_relationship": "benefits"})

    await repo.replace_graph(opp.id, nodes, edges)

    # 9. Link events
    event_links = [
        {
            "event_id":    ev.get("id", ""),
            "title":       ev.get("title", ""),
            "event_date":  str(ev.get("published_at", ""))[:10],
            "tag":         ev.get("category", "General"),
            "description": ev.get("summary", "")[:300],
            "importance":  1.0,
        }
        for ev in event_texts[:5]
    ]
    await repo.add_event_links(opp.id, event_links)

    await db.commit()
    logger.info("Generated opportunity id=%s slug=%s score=%s", opp.id, slug, score)
    return opp


"""
Typed evidence collection for the AI Search V3 pipeline.

Reuses the exact same trigger regexes and underlying real-data services as
V2's inline evidence-gathering block in ai_search_service.py (run_ai_search,
~lines 1808-2113) — imported directly, not re-implemented — so this module's
existence provably cannot change V2's behavior. V2 stays byte-for-byte
untouched throughout Phase 1; this is purely additive.

Never invents evidence: every block hits a real DB/service call and fails
silently on error (same resilience contract as V2), so a missing source
degrades gracefully instead of blocking the response or fabricating data.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_search import cache as cache_mod
from app.services.ai_search_service import (
    _MACRO_TRIGGER,
    _OPPORTUNITY_TRIGGER,
    _RESULTS_TRIGGER,
    _RISK_TRIGGER,
    _SECTOR_TRIGGER,
    _THEME_TRIGGER,
    _VALUATION_TRIGGERS,
    _VIX_TRIGGER,
    _fetch_valuation_sync,
    _fetch_vix_sync,
    _infer_historical_category,
    _infer_historical_sectors,
    _search_events,
    _search_news,
    _search_policies,
    _words,
)

log = structlog.get_logger(__name__)


@dataclass
class EvidenceBundle:
    events: list[dict] = field(default_factory=list)
    news: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    valuation: dict = field(default_factory=dict)
    vix_level: float | None = None
    mie_state: dict = field(default_factory=dict)
    similar_historical: list[dict] = field(default_factory=list)
    sector_rows: list[dict] = field(default_factory=list)
    opportunities: list[dict] = field(default_factory=list)
    themes: list[dict] = field(default_factory=list)
    risk_score: float | None = None
    risk_context: dict = field(default_factory=dict)
    macro_indices: list[dict] = field(default_factory=list)
    company_story: str | None = None
    announcements: list[dict] = field(default_factory=list)
    results_announcements: list[dict] = field(default_factory=list)
    # Ordered, human-readable evidence lines — the *view* of this bundle used
    # for prompt injection (mirrors V2's extra_context string exactly).
    context_lines: list[str] = field(default_factory=list)

    @property
    def source_count(self) -> int:
        return len(self.events) + len(self.news) + len(self.policies)

    def to_context_text(self) -> str:
        return "\n\n".join(self.context_lines)

    def to_source_ids(self) -> list[str]:
        """Stable evidence IDs for source-attribution tagging."""
        ids = [f"event:{e.get('id')}" for e in self.events if e.get("id")]
        ids += [f"news:{n.get('id')}" for n in self.news if n.get("id")]
        ids += [f"policy:{p.get('id')}" for p in self.policies if p.get("id")]
        ids += [f"historical:{h.get('id')}" for h in self.similar_historical if h.get("id")]
        return ids

    def evidence_checklist(self) -> dict[str, bool]:
        """Backing categories shown to the user (Evidence Score checklist)."""
        return {
            "real_time_price_data": bool(self.valuation or self.vix_level or self.macro_indices),
            "government_data": bool(self.policies),
            "historical_precedent": bool(self.similar_historical),
            "company_filings": bool(self.announcements or self.results_announcements),
            "live_market_events": bool(self.events or self.news),
        }


async def collect(query: str, intent_data: dict, entities: dict, db: AsyncSession) -> EvidenceBundle:
    """Gathers every real evidence source V2 uses, gated by the identical
    trigger regexes, into one typed bundle a specialist prompt can consume."""
    bundle = EvidenceBundle()
    loop = asyncio.get_running_loop()

    # Policy search is a pure function of the query's normalized word set
    # (see _search_policies — it filters GovernmentPolicy.title by exactly
    # those words), so caching on that same word set is a safe, correct
    # memoization, not an approximation: two queries with an identical
    # word set are guaranteed to hit the identical DB filter.
    policy_sig = "+".join(sorted(set(_words(query))))

    async def _policies_factory():
        return await _search_policies(db, query)

    events, news, policies = await asyncio.gather(
        _search_events(db, query), _search_news(db, query),
        cache_mod.component("policy", policy_sig, _policies_factory),
        return_exceptions=True,
    )
    bundle.events = events if isinstance(events, list) else []
    bundle.news = news if isinstance(news, list) else []
    bundle.policies = policies if isinstance(policies, list) else []

    if _VALUATION_TRIGGERS.search(query):
        co_syms = [c.upper() for c in entities.get("companies", [])[:2]]
        if co_syms:
            try:
                bundle.valuation = await loop.run_in_executor(None, _fetch_valuation_sync, co_syms)
                for sym, v in bundle.valuation.items():
                    parts = []
                    if v.get("pe"):
                        parts.append(f"P/E {v['pe']}")
                    if v.get("pb"):
                        parts.append(f"P/B {v['pb']}")
                    if v.get("52w_high") and v.get("52w_low"):
                        parts.append(f"52W {v['52w_low']}-{v['52w_high']}")
                    if parts:
                        bundle.context_lines.append(f"{sym}: {', '.join(parts)}")
            except Exception:
                pass

    try:
        bundle.vix_level = await loop.run_in_executor(None, _fetch_vix_sync)
        if bundle.vix_level and _VIX_TRIGGER.search(query):
            bundle.context_lines.append(f"India VIX current level: {bundle.vix_level}")
    except Exception:
        pass

    try:
        from app.services.intelligence.engine import get_intelligence_state
        mie = await get_intelligence_state()
        bundle.mie_state = mie
        intel_lines: list[str] = []
        signals = mie.get("signals", {})
        if signals.get("mood") and signals.get("direction"):
            intel_lines.append(
                f"[MARKET MOOD] {signals['mood']} · {signals['direction'].upper()} · "
                f"Risk: {signals.get('risk_level', 'MODERATE')} · "
                f"AI confidence: {signals.get('confidence', 0)}%"
            )
        if signals.get("top_theme"):
            intel_lines.append(f"[TOP THEME] {signals['top_theme']} (score {signals.get('top_theme_score', 0):.0f})")
        top_evts = [e for e in mie.get("top_events", []) if e.get("urgency", 0) >= 5][:6]
        for e in top_evts:
            intel_lines.append(f"[LIVE URGENCY {e['urgency']}/10] {e.get('one_liner') or e.get('headline', '')[:120]}")
        if intel_lines:
            bundle.context_lines.append("LIVE MARKET INTELLIGENCE (MIE):\n" + "\n".join(intel_lines))
    except Exception:
        pass

    try:
        from app.services.historical_memory_service import find_similar_events, format_for_ai_prompt
        hist_sectors: list[str] = []
        hist_category = None
        for ev in (bundle.events or [])[:3]:
            hist_sectors.extend(ev.get("affected_sectors", ev.get("sectors", [])) or [])
            if not hist_category:
                hist_category = ev.get("event_type") or ev.get("category")
        q_lower = query.lower()
        hist_query = {
            "category": _infer_historical_category(q_lower) or hist_category,
            "sectors": _infer_historical_sectors(q_lower) or list(dict.fromkeys(hist_sectors))[:4],
            "sentiment": intent_data.get("sentiment"),
        }
        if hist_query.get("category") or hist_query.get("sectors"):
            hist_sig = (
                f"{hist_query.get('category') or ''}|"
                f"{','.join(sorted(hist_query.get('sectors') or []))}|"
                f"{hist_query.get('sentiment') or ''}"
            )

            async def _hist_factory():
                return await find_similar_events(hist_query, limit=5, min_similarity=25.0)

            bundle.similar_historical = await cache_mod.component("historical", hist_sig, _hist_factory)
            if bundle.similar_historical:
                bundle.context_lines.append(format_for_ai_prompt(bundle.similar_historical, max_events=5))
    except Exception:
        pass

    if _SECTOR_TRIGGER.search(query):
        try:
            from app.services.market_data import get_sector_changes
            bundle.sector_rows = await cache_mod.component("sector", "all", get_sector_changes)
            q_lower = query.lower()
            named = [
                s for s in bundle.sector_rows
                if any(tok in q_lower for tok in s.get("name", "").lower().split() if len(tok) > 3)
            ]

            def _abs_pct(s: dict) -> float:
                try:
                    return abs(float(str(s.get("value", "0")).replace("%", "").replace("+", "")))
                except (ValueError, TypeError):
                    return 0.0

            shown = sorted(named or bundle.sector_rows, key=_abs_pct, reverse=True)[:5]
            if shown:
                bundle.context_lines.append(
                    "Sector performance (real, live 1-day change): "
                    + "; ".join(f"{s['name']} {s['value']}" for s in shown)
                )
        except Exception:
            pass

    if _OPPORTUNITY_TRIGGER.search(query):
        try:
            from app.services.opportunity_service import OpportunityService
            terms = (entities.get("companies") or []) + _words(query)
            bundle.opportunities = await OpportunityService(db).list_by_sector_or_theme(terms[:6], limit=5)
            if bundle.opportunities:
                bundle.context_lines.append(
                    "Verified opportunities (real, from the Opportunity Engine): "
                    + "; ".join(
                        f"{o['title']} (score {o['opportunity_score']}, {o['confidence']} confidence, "
                        f"trend {o['trend']}, risk {o['risk_level']})" for o in bundle.opportunities
                    )
                )
        except Exception:
            pass

    if _THEME_TRIGGER.search(query):
        try:
            from app.services.intelligence.engine import read_themes
            themes = await read_themes()
            q_lower = query.lower()
            named = [
                t for t in themes
                if any(tok in q_lower for tok in (t.get("theme") or "").lower().split() if len(tok) > 3)
            ]
            bundle.themes = (named or themes)[:3]
            if bundle.themes:
                lines = []
                for t in bundle.themes:
                    stocks = ", ".join(
                        (s.get("sym", "") if isinstance(s, dict) else str(s))
                        for s in (t.get("top_stocks") or [])[:3]
                    )
                    lines.append(
                        f"{t.get('theme', 'Theme')} (momentum {t.get('momentum', 'n/a')})"
                        + (f" — top stocks: {stocks}" if stocks else "")
                    )
                bundle.context_lines.append("Live themes (real, from Theme Engine): " + "; ".join(lines))
        except Exception:
            pass

    if _RISK_TRIGGER.search(query) or intent_data.get("intent") == "sell":
        try:
            from app.services.market_data import get_sector_changes
            from app.services.market_scoring_engine import score_risk
            risk_sectors = bundle.sector_rows or await get_sector_changes()

            def _pct(s: dict) -> float:
                try:
                    return float(str(s.get("value", "0")).replace("%", "").replace("+", ""))
                except (ValueError, TypeError):
                    return 0.0

            lagging = sorted(risk_sectors, key=_pct)[:3]
            bearish_high_urgency = sum(
                1 for e in (bundle.mie_state.get("top_events") or [])
                if e.get("sentiment") == "bearish" and (e.get("urgency") or 0) >= 7
            )
            entity_bearish = 0
            if entities.get("companies"):
                _sym = entities["companies"][0].upper()
                entity_bearish = sum(
                    1 for e in (bundle.mie_state.get("top_events") or [])
                    if e.get("sentiment") == "bearish" and (
                        _sym in [str(t).upper() for t in (e.get("tickers") or [])]
                        or _sym in (str(e.get("headline", "")) + " " + str(e.get("one_liner") or "")).upper()
                    )
                )
            bundle.risk_score = score_risk(float(bundle.vix_level or 0), bearish_high_urgency, lagging, entity_bearish)
            bundle.risk_context = {
                "bearish_high_urgency": bearish_high_urgency,
                "lagging_sectors": lagging,
                "entity_bearish": entity_bearish,
            }
            entity_note = (
                f" · {entity_bearish} bearish events specific to {entities['companies'][0]}"
                if entity_bearish else ""
            )
            bundle.context_lines.append(
                f"Computed Risk Score (real, deterministic formula): {bundle.risk_score}/100 · "
                f"India VIX {bundle.vix_level or 'n/a'} · {bearish_high_urgency} high-urgency bearish market events · "
                f"weakest sectors: {', '.join(s['name'] for s in lagging) or 'none'}{entity_note}"
            )
        except Exception:
            pass

    if _MACRO_TRIGGER.search(query):
        try:
            from app.services.market_data import get_extended_indices
            idx_rows = await get_extended_indices()
            bundle.macro_indices = [i for i in idx_rows if i.get("name") in ("NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX")]
            if bundle.macro_indices:
                bundle.context_lines.append(
                    "Macro indices (real, live): "
                    + "; ".join(f"{i['name']} {i['value']} ({i['change']})" for i in bundle.macro_indices)
                )
        except Exception:
            pass

    if intent_data.get("intent") == "general" and not intent_data.get("is_comparison") and len(entities.get("companies") or []) == 1:
        try:
            from app.services.intelligence.engine import get_symbol_context
            from app.services.company_announcements_service import get_recent_announcements
            sym = entities["companies"][0]

            async def _company_intel_factory():
                raw_ctx, raw_ann = await asyncio.gather(
                    get_symbol_context(sym), get_recent_announcements(sym, limit=5), return_exceptions=True,
                )
                return {
                    "ctx": raw_ctx if not isinstance(raw_ctx, BaseException) else None,
                    "ann": raw_ann if not isinstance(raw_ann, BaseException) else None,
                }

            intel = await cache_mod.component("company", sym, _company_intel_factory)
            ctx, ann = intel.get("ctx"), intel.get("ann")
            if isinstance(ctx, dict) and ctx.get("story"):
                story_val = ctx["story"]
                story_text = story_val.get("text") if isinstance(story_val, dict) else str(story_val)
                if story_text:
                    bundle.company_story = story_text
                    block = f"Company context for {sym} (real, from Intelligence Graph): {story_text[:220]}"
                    if ctx.get("market_mood"):
                        block += f" · Mood: {ctx['market_mood']}"
                    bundle.context_lines.append(block)
            if isinstance(ann, list) and ann:
                bundle.announcements = ann
                ann_txt = "; ".join(
                    f"{a.get('subject', '')} ({a.get('category', '')}, {a.get('announcement_date', '')})" for a in ann[:5]
                )
                bundle.context_lines.append(f"Recent real filed announcements for {sym}: {ann_txt}")
        except Exception:
            pass

    if _RESULTS_TRIGGER.search(query):
        try:
            from app.services.company_announcements_service import get_recent_announcements
            for sym in (entities.get("companies") or [])[:2]:
                ann = await get_recent_announcements(sym, limit=8)
                results_ann = [a for a in ann if any(k in (a.get("category", "") or "").lower() for k in ("result", "financial"))]
                if results_ann:
                    bundle.results_announcements.extend(results_ann)
                    lines = "; ".join(f"{a['subject']} ({a['announcement_date']})" for a in results_ann[:3])
                    bundle.context_lines.append(f"Real filed results announcements for {sym}: {lines}")
        except Exception:
            pass

    return bundle

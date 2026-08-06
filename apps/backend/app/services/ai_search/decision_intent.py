"""
Decision-intent classification (routing-tier regex classifier — a distinct
concept from this package's own intent.py, which resolves comparison
entities, not intent category), shared by both AI Search pipelines (V2:
ai_search_service.py, V3: this package) — extracted verbatim from
ai_search_service.py during P5 Stage 1 (2026-08-06), zero behavior change.
Deliberately named decision_intent.py, not intent.py, to avoid conflating
the two.
"""
from __future__ import annotations

import re

from app.services.ai_search.regexes import _COMMODITY_NAMES

_DECISION_INTENTS = {
    # "move from" needed "move" directly before "from" — missed "move
    # INVESTMENT from X to Y" (found live). (?:\s+\w+){0,3} tolerates
    # filler words in between, same fix family as switch-from-to below.
    "switch":           [r"\bswitch(?:ing)?\b", r"\brotate?\b", r"\binstead of\b", r"\bsell.{1,30}buy\b", r"\bmove\b(?:\s+\w+){0,3}\s+from\b", r"\breplace\b"],
    "hold":             [r"\bshould i hold\b", r"\bkeep holding\b", r"\bcontinue holding\b", r"\bstill hold\b", r"\bhold or sell\b"],
    "compare":          [r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b", r"\bbetter than\b", r"\bwhich is better\b", r"\bwhich (?:one|company|stock)\b"],
    "sell":             [r"\bshould i sell\b", r"\bwhen to sell\b", r"\bexit\b", r"\bbook (?:profit|loss)\b"],
    # "top \d+ stocks" alone missed any real-world phrasing with a sector/
    # theme qualifier between the count and the noun ("top 5 BANKING
    # stocks") — (?:\w+\s+){0,4} tolerates multi-word qualifiers in between
    # (found live: "top 5 EV AND DEFENCE stocks" needed {0,4}, not {0,2}),
    # same fix pattern as the switch-from-to gap found this session. The
    # last two patterns cover "best/top X stocks" with NO count at all
    # (also found live — "best defence companies", "best AI stocks") —
    # plural-only to avoid false-triggering on singular "the best stock to
    # buy" type single-entity decision queries.
    "list_picks":       [r"\bgive me \d+\b", r"\btop \d+ (?:\w+\s+){0,4}(?:stocks?|picks?|companies|shares)\b", r"\bbest \d+ (?:\w+\s+){0,4}(?:stocks?|picks?|companies|shares)\b", r"\brecommend \d+\b", r"\b\d+ best (?:stocks?|picks?)\b", r"\bwhich \d+ (?:\w+\s+){0,4}(?:stocks?|picks?)\b", r"\bbest (?:\w+\s+){0,3}(?:stocks|picks|companies|shares)\b", r"\btop (?:\w+\s+){0,3}(?:stocks|picks|companies|shares)\b"],
    "news_reaction":    [r"\bjust (?:announced|reported|won|got|received|published)\b", r"\bafter.*q[1-4].*results?\b", r"\bq[1-4].*results?.*\bwhat\b", r"\bbreaking.*market\b", r"\breaction to\b", r"\bwhat (?:should i do|does this mean|now)\b.*\b(?:won|lost|beat|missed|announced)\b"],
    "earnings_preview": [r"\bbefore (?:earnings|results|q[1-4])\b", r"\bpre.?(?:earnings|results?)\b", r"\bahead of (?:earnings|results?)\b", r"\bearnings (?:this|next) (?:week|month)\b"],
    "entry_timing":     [r"\bgood time to enter\b", r"\bright time to (?:buy|invest)\b", r"\bentry (?:point|level|price)\b", r"\bwhen (?:to|should i) enter\b"],
    "portfolio_review": [r"\bmy portfolio\b", r"\bconcentration risk\b", r"\basset allocation\b", r"\brebalance\b", r"\bportfolio (?:is|has|with)\b", r"\bi (?:own|hold|have) .+,"],
    "buy":              [r"\bshould i buy\b", r"\bgood time to buy\b", r"\bworth buying\b", r"\bcan i buy\b"],
    "decision":         [r"\bshould i\b", r"\bworth it\b", r"\bgood investment\b", r"\bsafe to invest\b"],
}

_HOLDING_RE = re.compile(
    r"(?:i (?:hold|own|have|bought|invested in|am holding|currently hold|am in)|"
    r"my (?:investment|portfolio|position|holding) (?:in|of)|"
    r"i already (?:have|own|hold)|"
    r"i (?:am planning to sell|want to sell))\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?| and | should)",
    re.IGNORECASE,
)
_TARGET_RE = re.compile(
    r"(?:(?:buy|switch to|move to|invest in|purchase|rotate to|into)\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?| instead| rather| now)|"
    r"(?:and buy|to buy|or buy)\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?))",
    re.IGNORECASE,
)
_HORIZON_RE = re.compile(
    r"\b(\d+[-\s](?:month|year|week)s?|short.?term|medium.?term|long.?term|"
    r"1\s*month|3\s*months?|6\s*months?|1\s*year|3.5\s*years?)\b",
    re.IGNORECASE,
)
_RISK_RE = re.compile(
    r"\b(conservative|moderate|aggressive|low risk|high risk|safe)\b", re.IGNORECASE
)
_COMPARE_RE = re.compile(
    r"(?:is\s+)?([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+"
    r"(?:vs\.?|versus|better than|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
# Same as _COMPARE_RE plus "and" as a connector — "and" is too ambiguous a
# signal to trust in the general fallback (used for switch/hold/sell/buy/
# decision/general), but inside a query whose intent already contains the
# literal word "compare", "and" is the single most natural connector
# ("Compare TCS and Infosys" — found live, unmatched by the vs/versus/or
# original) and safe to accept there.
_COMPARE_RE_AND = re.compile(
    r"(?:is\s+)?([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+"
    r"(?:vs\.?|versus|better than|or|and)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
_SWITCH_FROM_TO_RE = re.compile(
    r"(?:switch|rotate|move)(?:ing)?(?:\s+\w+){0,3}\s+(?:(?:out\s+of|away\s+from)|from)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{1,30}?)\s+(?:to|into|for)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{1,30}?)(?:\.|,|$|\?| now| instead)",
    re.IGNORECASE,
)
_COMPARE_RE_3 = re.compile(
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+(?:vs\.?|versus|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+(?:vs\.?|versus|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"₹\s*([\d,]+)\s*(lakh|crore|thousand|k)?|(\d+)\s*(lakh|crore|thousand)\b",
    re.IGNORECASE,
)
_SECTOR_NAMES = {
    "banking", "it", "technology", "defence", "energy", "pharma", "auto",
    "fmcg", "metals", "realty", "telecom", "power", "finance", "logistics",
    "infrastructure", "railway", "railways", "healthcare", "consumption",
    "manufacturing", "chemicals", "fertilizers", "insurance",
}


def _detect_decision_intent(query: str) -> dict:
    q = query.lower()
    detected_intent = "general"
    for intent, patterns in _DECISION_INTENTS.items():
        if any(re.search(p, q) for p in patterns):
            detected_intent = intent
            break

    is_decision = detected_intent != "general"

    holding = None
    m = _HOLDING_RE.search(query)
    if m:
        holding = m.group(1).strip()

    target = None
    m2 = _TARGET_RE.search(query)
    if m2:
        target = (m2.group(1) or m2.group(2) or "").strip()

    # Compare: try 3-way first, then 2-way
    third_entity = None
    if detected_intent == "compare":
        mc3 = _COMPARE_RE_3.search(query)
        if mc3:
            holding = mc3.group(1).strip()
            target  = mc3.group(2).strip()
            third_entity = mc3.group(3).strip()
        elif not holding and not target:
            # _COMPARE_RE_AND (not the shared _COMPARE_RE) — "and" is only
            # trusted as a connector here, where the query already contains
            # the literal word "compare" ("Compare TCS and Infosys" — found
            # live, unmatched by vs/versus/better-than/or alone).
            mc = _COMPARE_RE_AND.search(query)
            if mc:
                holding = re.sub(r"^compare\s+(?:the\s+)?", "", mc.group(1).strip(), flags=re.IGNORECASE)
                target  = mc.group(2).strip()
    elif detected_intent == "switch" and not holding and not target:
        # "switch/rotate/move FROM X TO Y" — the single most natural way to
        # phrase a switch decision, and previously unhandled: _HOLDING_RE
        # needs first-person possession language ("I hold X"), _TARGET_RE
        # needs "switch TO X" (not "FROM X TO Y"), and _COMPARE_RE needs a
        # vs/versus/or connector. All three miss this phrasing, so is_comparison
        # silently came out False and the whole decision-comparison path
        # (including the Decision Engine) never ran for it.
        msft = _SWITCH_FROM_TO_RE.search(query)
        if msft:
            holding = msft.group(1).strip()
            target  = msft.group(2).strip()
        else:
            mc = _COMPARE_RE.search(query)
            if mc:
                holding = mc.group(1).strip()
                target  = mc.group(2).strip()
    elif detected_intent in ("hold", "sell", "buy", "decision", "general") and not holding and not target:
        # Fallback: try compare regex for "X vs Y" / "X or Y" phrasing even
        # when no decision-intent keyword fired at all — "HDFC or ICICI?"
        # (found live) previously stayed intent=general with is_comparison
        # never even attempted, because "general" wasn't in this tuple.
        # _COMPARE_RE's connector list already requires a real structural
        # signal (vs/versus/better than/or), so this is safe to attempt
        # unconditionally rather than gating it behind a specific intent.
        mc = _COMPARE_RE.search(query)
        if mc:
            holding = mc.group(1).strip()
            target  = mc.group(2).strip()

    horizon = None
    m3 = _HORIZON_RE.search(query)
    if m3:
        horizon = m3.group(1)

    risk = None
    m4 = _RISK_RE.search(query)
    if m4:
        risk = m4.group(1)

    # Budget/amount extraction
    budget = None
    mb = _BUDGET_RE.search(query)
    if mb:
        amt_str = ((mb.group(1) or mb.group(3)) or "").replace(",", "")
        unit    = ((mb.group(2) or mb.group(4)) or "").lower()
        if amt_str:
            try:
                amt = float(amt_str)
                if unit in ("lakh",):
                    budget = f"₹{amt:.0f} lakh"
                elif unit in ("crore",):
                    budget = f"₹{amt:.0f} crore"
                elif unit in ("thousand", "k"):
                    budget = f"₹{amt * 1000:.0f}"
                else:
                    budget = f"₹{amt_str}"
            except ValueError:
                pass

    # Count for list_picks
    pick_count = 3
    if detected_intent == "list_picks":
        cm = re.search(r"\b(\d+)\b", query)
        if cm:
            pick_count = min(int(cm.group(1)), 10)

    # Sector entity detection — flag when holding/target is a sector, not a company
    holding_is_sector    = bool(holding and holding.lower().strip() in _SECTOR_NAMES)
    target_is_sector     = bool(target  and target.lower().strip()  in _SECTOR_NAMES)
    # Commodity/asset class detection — Gold, Silver, Nifty, crypto, bonds, etc.
    holding_is_commodity = bool(holding and holding.lower().strip() in _COMMODITY_NAMES)
    target_is_commodity  = bool(target  and target.lower().strip()  in _COMMODITY_NAMES)

    # Portfolio extraction for multi-stock queries
    portfolio: list[str] = []
    if detected_intent == "portfolio_review":
        pm = re.search(
            r"(?:i (?:own|hold|have)|portfolio (?:is|has|includes?))[^\w]+"
            r"((?:[A-Za-z][A-Za-z0-9 &.]+(?:,\s*|\s+and\s+)){1,5}[A-Za-z][A-Za-z0-9 &.]+)",
            query, re.IGNORECASE,
        )
        if pm:
            raw = pm.group(1)
            portfolio = [p.strip() for p in re.split(r",\s*|\s+and\s+", raw) if p.strip()][:6]

    # A genuine two-asset comparison needs BOTH sides actually named by the
    # user — "should I invest in defence stocks" only ever fills `target`
    # (via the "invest in X" pattern), never `holding`. Without this check,
    # the decision-comparison prompt used to fabricate a placeholder
    # "Asset A" / RELIANCE holding and frame every single-entity question as
    # a two-way switch decision nobody asked for.
    is_comparison = bool(holding) and bool(target)

    return {
        "is_decision":       is_decision,
        "is_comparison":     is_comparison,
        "intent":            detected_intent,
        "holding":           holding,
        "target":            target,
        "third_entity":      third_entity,
        "horizon":           horizon,
        "risk":              risk,
        "budget":            budget,
        "pick_count":        pick_count,
        "holding_is_sector":    holding_is_sector,
        "target_is_sector":     target_is_sector,
        "holding_is_commodity": holding_is_commodity,
        "target_is_commodity":  target_is_commodity,
        "portfolio":            portfolio,
    }

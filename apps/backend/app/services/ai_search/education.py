"""
Educational / product-knowledge contract (Step 4B).

Questions like "What is a P/E ratio?", "What does FII selling mean?" and "How does the MarketRipple Score work?" used to take the evidence-free explanation path: no Gate A (nothing to gate), Gate B not
applicable, and a generic model answering from memory. For a definition that is harmless; for a MarketRipple PRODUCT question it is not (the model could invent pillars, weights or interpretation bands).

This module is the smallest explicit contract for the questions it recognises, with no model call at all:
  * GENERAL EDUCATION (P/E ratio, FII flows): a fixed, owner-written explanation. It is plainly educational, carries no market or company figure, makes no forecast and gives no recommendation, and
    never presents itself as current market evidence.
  * PRODUCT KNOWLEDGE (MarketRipple Score): a fixed answer taken only from MarketRipple's own published methodology page. Nothing is added, so nothing can be invented. A request for detail the published
    methodology does not contain (formulas, metric-level weights, back-tests, predictive accuracy) is answered with an explicit "not part of the published methodology" notice, not a guess.

What does NOT use this contract (it falls through to the existing evidence-gated pipeline): any question that names a company, sector or policy, asks for current or numeric data (today, current, latest, how
much, a price or level, any digit), or covers more than one topic. That is how "What is TCS's current P/E?", "How much did FIIs sell today?" and "What is TCS's MarketRipple Score?" keep needing evidence.

Wording note: the published methodology says "not a buy/sell recommendation" and the glossary says FIIs "buy and sell" securities. The public safety gate rejects the bare words buy and sell wherever
they appear and is NOT bypassed for these answers, so those sentences are reworded here with the same meaning ("not a recommendation about any stock", "trade Indian securities").

Sources (kept in sync by tests/services/test_ai_search_education.py):
  glossary  apps/web/lib/glossary-data.ts   slugs "pe-ratio", "fii", "dii"   (MarketRipple's written definitions)
  methodology  apps/web/app/(knowledge)/methodology/marketripple-score/page.tsx as DEPLOYED on origin/main (commit 8bbe68b, page last changed in 7eb263d). The copy of that page in the
               release/ai-answer-v2 working tree is the older "Banking V1" version and is NOT used; re-verify when the branch is merged with main.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

KIND_GENERAL = "general_education"
KIND_PRODUCT = "product_knowledge"

# ── recognition ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

_DEFINITIONAL = re.compile(
    r"^\s*(?:what\s+(?:is|are|does|do)|explain|define|how\s+(?:does|do|should\s+i\s+(?:read|use|interpret)|to\s+read)|meaning\s+of|tell\s+me\s+about)(?![a-z])", re.IGNORECASE)

# Anything that asks about NOW, a quantity or a price is a data question, never an education question. Also used by the retrieval plan so such a question cannot take the evidence-free explanation plan.
CURRENT_DATA_RE = re.compile(
    r"\d|(?<![a-z])(?:today|tonight|tomorrow|yesterday|now|currently|current|latest|live|recent(?:ly)?|this\s+(?:week|month|quarter|year|session)|last\s+(?:week|month|quarter|year|session)|"
    r"at\s+the\s+moment|as\s+of|how\s+much|how\s+many|price|prices|level|levels|trading|closed|closing|figure|figures|number|numbers)(?![a-z])", re.IGNORECASE)

_TOPIC_PATTERNS = {
    "pe_ratio": re.compile(r"p\s*/\s*e(?![a-z])|(?<![a-z])pe\s+(?:ratio|multiple)(?![a-z])|price[\s-]+(?:to|/)[\s-]*earnings", re.IGNORECASE),
    "fii_flows": re.compile(r"(?<![a-z])(?:fiis?|fpis?)(?![a-z])|foreign\s+(?:institutional|portfolio)\s+investors?", re.IGNORECASE),
    "marketripple_score": re.compile(r"market\s*ripple\s+score", re.IGNORECASE),
}

# The question tries to turn an explanation into a forecast or a recommendation: the answer stays educational and says so.
_ADVICE = re.compile(
    r"(?:should|can|could|shall)\s+i\s+(?:buy|sell|hold|invest|bet|put)|(?<![a-z])(?:buy|sell|invest\s+in)(?![a-z])|(?<![a-z])(?:will|going\s+to|gonna)(?![a-z]).{0,40}(?<![a-z])(?:rise|fall|crash|rally|go\s+up|go\s+down|drop|increase|decrease|recover|beat)|"
    r"(?<![a-z])(?:predict|forecast|outlook|expected\s+returns?|returns?)(?![a-z])", re.IGNORECASE)

# A MarketRipple Score question that wants more than the published methodology contains.
_BEYOND_PUBLISHED = re.compile(
    r"formula|algorithm|source\s+code|exact(?:ly)?\s+(?:calculat|how|weight|formula)|how\s+is\s+(?:it|the\s+score|the\s+marketripple\s+score)\s+calculated|"
    r"(?:metric|input|indicator)[\s-]+(?:level\s+)?weights?|weigh\w*\s+(?:each|every|the)\s+(?:metric|input|indicator)s?|weights?\s+(?:of|for)\s+(?:each|the)\s+(?:metric|input|indicator)|per[\s-]metric|back[\s-]?test|accuracy|track\s+record|"
    r"predictive\s+(?:power|value)|hidden|secret|undisclosed|proprietary", re.IGNORECASE)


# A MarketRipple Score question may be phrased in any interrogative form ("Is it a buy signal?", "Does a high score mean it will rise?"): the answer is the published definition either way, with the
# not-a-prediction / not-a-recommendation statement made explicit.
_PRODUCT_INTERROGATIVE = re.compile(r"^\s*(?:what|how|why|does|do|is|are|can|could|will|should|tell|explain|define|meaning)(?![a-z])", re.IGNORECASE)


def topic_for(query: str, entities: dict | None) -> str | None:
    """The one curated topic this query is a plain educational/product question about, else None. Conservative: any doubt means None and the question stays on the evidence-gated pipeline."""
    q = query or ""
    ents = entities or {}
    if ents.get("companies") or ents.get("sectors") or ents.get("policies"):
        return None
    if CURRENT_DATA_RE.search(q):
        return None
    found = [name for name, pat in _TOPIC_PATTERNS.items() if pat.search(q)]
    if len(found) != 1:
        return None
    shaped = _PRODUCT_INTERROGATIVE if found[0] == "marketripple_score" else _DEFINITIONAL
    return found[0] if shaped.search(q) else None


# ── curated content ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Topic:
    id: str
    kind: str
    title: str
    summary: str
    bottom_line: str
    points: tuple[tuple[str, str, str], ...]          # (icon keyword, title, text)
    grounding: str                                    # public name of the source
    source_ref: str                                   # plain-text attribution (never a link off-site)
    authored_for_contract: tuple[str, ...] = field(default_factory=tuple)      # sentences written for this contract, not copied from the owner's source (owner review item)


TOPICS: dict[str, Topic] = {
    "pe_ratio": Topic(
        id="pe_ratio", kind=KIND_GENERAL, title="P/E ratio (price-to-earnings)",
        summary=("The P/E ratio is a stock's share price divided by its earnings per share. It tells you how many rupees investors are willing to pay for every one rupee of a company's current annual profit."),
        bottom_line=("This is a general explanation of the term. It does not describe any company's current P/E, and it is not a forecast or a recommendation. For a specific company's P/E, ask about that company."),
        points=(
            ("valuation", "What it shows", "A P/E of 25 means the market is valuing the stock at 25 times its earnings (the glossary's own illustration, not any company's figure)."),
            ("valuation", "Reading a high or low P/E", "A higher P/E generally reflects higher expected future growth (or, sometimes, overvaluation). A lower P/E can mean the stock is undervalued, or that the market expects earnings to decline."),
            ("valuation", "Compare, do not read it alone", "P/E is only meaningful when compared: against the company's own historical average, against direct sector peers, or against the broader index. A P/E of 40 might be cheap for a fast-growing tech company and expensive for a slow-growing utility."),
            ("risk", "Limits", "P/E is one valuation measure, not a verdict. Earnings can include one-off items, such as exceptional gains or losses, that distort the ratio, and differences in sector and growth change what a given P/E means."),
        ),
        grounding="MarketRipple glossary", source_ref="marketripple:glossary/pe-ratio",
        authored_for_contract=("P/E is one valuation measure, not a verdict. Earnings can include one-off items, such as exceptional gains or losses, that distort the ratio, and differences in sector and growth change what a given P/E means.",),
    ),
    "fii_flows": Topic(
        id="fii_flows", kind=KIND_GENERAL, title="FII selling",
        summary=("FIIs (Foreign Institutional Investors, also called FPIs or Foreign Portfolio Investors) are large foreign entities that trade Indian securities. FII selling means they are selling Indian securities; "
                 "when their selling exceeds their buying in a session it is reported as net selling."),
        bottom_line=("This explains the concept. It does not report how much FIIs bought or sold on any day, and it is not a market forecast. Current flows need current data for a specific period."),
        points=(
            ("policy", "Why it is watched", "Because they move large sums relative to daily trading volumes, sustained FII buying or selling can meaningfully move the Nifty and the rupee. FII flow data is watched closely as a sentiment indicator for how global capital views India relative to other emerging markets."),
            ("policy", "Typical effect", "Net selling by FIIs is generally a headwind for the market, all else equal."),
            ("risk", "Limits", "FII flows are sensitive to global factors well beyond India-specific news: US interest rates, dollar strength, and risk appetite across all emerging markets all influence whether foreign money is flowing in or out."),
            ("risk", "Domestic institutions can offset it", "DIIs are Domestic Institutional Investors, India-based institutions such as mutual funds and insurers. When DIIs absorb FII selling by investing roughly the same amount, the market often stays range-bound rather than falling sharply."),
        ),
        grounding="MarketRipple glossary", source_ref="marketripple:glossary/fii, marketripple:glossary/dii",
    ),
    "marketripple_score": Topic(
        id="marketripple_score", kind=KIND_PRODUCT, title="MarketRipple Score",
        summary=("The MarketRipple Score is a 0-100 company assessment built from three weighted pillars, Financial Strength, Valuation and Market Behaviour, using the same formula and rating scale for every supported sector, "
                 "bank or non-bank. A score is published only once minimum evidence requirements are satisfied."),
        bottom_line=("A higher score represents stronger conditions across the factors MarketRipple evaluates. It is not a prediction of future share-price returns and not a recommendation about any stock."),
        points=(
            ("valuation", "Three weighted pillars", "The weights are fixed: Financial Strength 8/15, Valuation 4/15 and Market Behaviour 3/15. All three must be available or no headline number is shown at all; MarketRipple never blends a subset of them with adjusted weights."),
            ("valuation", "Current Intelligence is separate", "Real evidence from MarketRipple's event and company-intelligence system appears in full on every company page, but it structurally cannot affect the MarketRipple Score number."),
            ("valuation", "Sector-specific inputs", "Only the raw inputs to Financial Strength differ by sector. Banks are scored on bank metrics: Gross NPA %, Net NPA %, CET1 Ratio, ROA, ROE, NII Growth and Profit Growth. "
                                                    "Non-bank sectors use Revenue Growth %, Profit Growth %, ROE, ROCE, Debt-to-Equity and Interest Coverage. A bank is never scored on inventory turnover and a real-estate company is never scored on Net NPA."),
            ("valuation", "Which sectors", "The score covers Banking and 19 non-bank sectors. Finance and Insurance do not have an approved methodology yet and show a \"not yet supported\" state, never a fabricated score."),
            ("valuation", "Peer-relative", "Valuation and Financial Strength are measured against the other companies in the same sector, as a percentile. The score describes where a company stands among its peers, not an absolute grade."),
            ("valuation", "Rating labels", "Strong is 75 to 100, Positive is 60 to 74, Neutral is 45 to 59 and Cautious is 0 to 44."),
            ("valuation", "When a score is published", "A company needs at least 5 of 7 Financial Strength metrics for Banking (4 of 6 for a non-bank sector), at least 65% overall evidence coverage, a real eligible financial reporting period, and Financial Strength present. "
                                                       "Otherwise it shows \"MarketRipple Score unavailable\" with a reason; nothing is estimated to fill the gap."),
            ("risk", "Coverage is not confidence", "Evidence coverage shows how much of the expected evidence was available and eligible when the score was calculated. It does not say how certain MarketRipple is about its interpretation."),
        ),
        grounding="MarketRipple Score methodology", source_ref="marketripple:methodology/marketripple-score",
    ),
}

NOT_PUBLISHED_NOTICE = ("The published MarketRipple Score methodology does not include exact formulas, metric-level weights, back-tests or any measure of predictive accuracy, so they are not described here.")
ADVICE_NOTICE = ("This is an explanation only: it does not forecast markets or prices and does not recommend buying, selling or holding anything.")


# ── response ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def build_response(query: str, topic_id: str, *, schema_version: str | None, ui_mode: str | None, intent: str = "general") -> dict:
    """The complete public response for a curated question. Built on the shared key skeleton, then marked as a normal, non-degraded answer. No model, no evidence retrieval: the content is the contract."""
    from app.services.ai_search.degraded_shape import build_degraded_shape

    t = TOPICS[topic_id]
    advice = bool(_ADVICE.search(query or ""))
    beyond = t.kind == KIND_PRODUCT and bool(_BEYOND_PUBLISHED.search(query or ""))
    r = build_degraded_shape(
        query=query, response_id=str(uuid.uuid4()), schema_version=schema_version, specialist_kind="education", degraded_reason=None, summary=t.summary,
        source_attribution=[t.source_ref], intent=intent, ui_mode=ui_mode,
    )
    notices = ([NOT_PUBLISHED_NOTICE] if beyond else []) + ([ADVICE_NOTICE] if advice else [])
    r["synthesis_incomplete"] = False
    r["answer"].update(bottom_line=" ".join([t.bottom_line, *notices]), sources_count=0)
    r["key_drivers"] = [{"icon": icon, "title": title, "explanation": text} for icon, title, text in t.points]
    if beyond:
        r["key_drivers"].append({"icon": "risk", "title": "Not part of the published methodology", "explanation": NOT_PUBLISHED_NOTICE})
    r["education"] = {
        "kind": t.kind, "topic": t.id, "title": t.title, "grounding": t.grounding, "source": t.source_ref,
        "current_market_evidence": False, "advice_requested": advice, "beyond_published_detail": beyond,
        "authored_for_contract": list(t.authored_for_contract),
    }
    r["answer_authorization"] = {"applicable": False, "authorized": True, "reasons": [], "contract": "education"}
    return r


def public_text(response: dict) -> str:
    """Every sentence a curated response can show, for tests."""
    a = response.get("answer") or {}
    parts = [a.get("summary", ""), a.get("bottom_line", "")]
    parts += [f"{d.get('title', '')}. {d.get('explanation', '')}" for d in response.get("key_drivers") or []]
    return " ".join(p for p in parts if p)

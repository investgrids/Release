"""
MarketRipple AI Search Benchmark Dataset Generator.

Produces the permanent regression suite for AI Search: a large, tagged,
deduplicated question set spanning every major investor-question category,
plus a curated golden-question subset and a blank evaluation sheet.

Run:
    python generate_dataset.py

Outputs (into this directory):
    dataset.json          — full benchmark (2000-3000 questions)
    golden_questions.json — ~200 mission-critical questions
    evaluation_sheet.csv  — one row per question, scoring columns blank
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from data import (
    COMPANIES, SECTOR_NAMES, IPO_NAMES, EVENT_TEMPLATES, MACRO_TOPICS,
    POLICY_TOPICS, EARNINGS_SCENARIOS, HISTORICAL_EVENTS, THEMES,
    COMMODITIES, GLOBAL_EVENTS, RISK_TOPICS, BEGINNER_TERMS, ADVANCED_TERMS,
    PERSONAS, DIFFICULTIES, TIME_HORIZONS,
)

random.seed(20260725)  # deterministic output across regenerations

OUT_DIR = Path(__file__).parent
_seen: set[str] = set()
_next_id = 1


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


def _mk(question: str, category: str, intent: str, difficulty: str | None = None,
        persona: str | None = None, time_horizon: str | None = None) -> dict | None:
    """Build a tagged question record, returning None on duplicate."""
    global _next_id
    key = _norm(question)
    if key in _seen:
        return None
    _seen.add(key)
    rec = {
        "id": f"q{_next_id:05d}",
        "category": category,
        "difficulty": difficulty or random.choice(DIFFICULTIES),
        "intent": intent,
        "persona": persona or random.choice(PERSONAS),
        "time_horizon": time_horizon or random.choice(TIME_HORIZONS),
        "question": question,
    }
    _next_id += 1
    return rec


def _fill(records: list[dict], gen, target: int) -> None:
    """Pull unique records from generator `gen` (a callable producing one
    record or None per call) until `target` new unique records are added or
    the generator is exhausted."""
    added = 0
    misses = 0
    while added < target and misses < target * 50 + 500:
        rec = gen()
        if rec is None:
            misses += 1
            continue
        records.append(rec)
        added += 1


# ─────────────────────────────────────────────────────────────────────────
# 1. Company Analysis (250)
# ─────────────────────────────────────────────────────────────────────────
def gen_company_analysis(records: list[dict]) -> None:
    templates = [
        "Analyze {name}",
        "Is {name} overvalued?",
        "Is {name} undervalued right now?",
        "Should I buy {name} after earnings?",
        "What are the biggest risks for {name}?",
        "Is {sym} still attractive at current levels?",
        "What is the outlook for {name} over the next year?",
        "Should I hold {name} for the long term?",
        "Why is {name} stock falling today?",
        "Why is {name} stock rallying today?",
        "What's driving {name}'s stock price?",
        "Is {name} a good buy for a beginner investor?",
        "What does {name}'s balance sheet tell us?",
        "How is {name} positioned against competition?",
        "Is {name} a value trap?",
        "What is {name}'s competitive moat?",
        "Should I add {name} to my portfolio?",
        "Is now a good time to enter {name}?",
        "What is the fair value of {name}?",
        "Give me a fundamental analysis of {name}",
        "What is {sym}'s growth story for the next 5 years?",
        "Is {name} management trustworthy?",
        "What is the promoter holding trend in {name}?",
        "Is {name}'s debt level a concern?",
        "How does {name} make money?",
    ]

    def one():
        c = random.choice(COMPANIES)
        t = random.choice(templates)
        q = t.format(name=c[1], sym=c[0])
        return _mk(q, "Company Analysis", "Company")

    _fill(records, one, 250)


# ─────────────────────────────────────────────────────────────────────────
# 2. Company Comparison (200)
# ─────────────────────────────────────────────────────────────────────────
def gen_company_comparison(records: list[dict]) -> None:
    templates = [
        "{a} vs {b}",
        "{a} vs {b} — which is the better buy?",
        "Compare {a} and {b}",
        "Should I buy {a} or {b}?",
        "{a} or {b} for long-term investing?",
        "Which has better fundamentals, {a} or {b}?",
        "Which stock is cheaper on valuation — {a} or {b}?",
        "{a} versus {b}: which has stronger growth?",
        "Between {a} and {b}, which is the safer bet?",
        "How does {a} compare to {b} on margins?",
        "Which pays a better dividend, {a} or {b}?",
        "{a} and {b} — which has less debt?",
    ]

    def one():
        c1, c2 = random.sample(COMPANIES, 2)
        t = random.choice(templates)
        q = t.format(a=c1[0] if random.random() < 0.5 else c1[1], b=c2[0] if random.random() < 0.5 else c2[1])
        return _mk(q, "Company Comparison", "Comparison")

    _fill(records, one, 200)


# ─────────────────────────────────────────────────────────────────────────
# 3. Sector Analysis (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_sector_analysis(records: list[dict]) -> None:
    templates = [
        "Best {sector} stocks to buy now",
        "Outlook for the {sector} sector",
        "Is the {sector} sector overheated?",
        "Which {sector} stocks have the strongest fundamentals?",
        "What's driving the {sector} sector rally?",
        "Why is the {sector} sector underperforming?",
        "Top {sector} stocks for the next 3 years",
        "Which sectors benefit from lower interest rates?",
        "Which sectors benefit from a weaker rupee?",
        "Which sectors are most exposed to crude oil prices?",
        "Is it a good time to invest in {sector} stocks?",
        "What are the key risks for the {sector} sector?",
        "How is the {sector} sector positioned for the next budget?",
        "Which {sector} stocks are undervalued right now?",
    ]

    def one():
        s = random.choice(SECTOR_NAMES)
        t = random.choice(templates)
        q = t.format(sector=s)
        return _mk(q, "Sector Analysis", "Sector")

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 4. Event Impact (200)
# ─────────────────────────────────────────────────────────────────────────
def gen_event_impact(records: list[dict]) -> None:
    templates = [
        "{event} — what's the market impact?",
        "How does {event_lc} affect Indian markets?",
        "Which stocks benefit if {event_lc}?",
        "Which sectors are hurt by {event_lc}?",
        "What should investors do after {event_lc}?",
        "Impact of {event_lc} on my portfolio",
        "{event} — how should I position my portfolio?",
        "What's the ripple effect of {event_lc}?",
        "How will {event_lc} affect banking stocks?",
        "How will {event_lc} affect IT stocks?",
        "How will {event_lc} affect the rupee?",
        "Is {event_lc} priced in already?",
    ]

    def one():
        e = random.choice(EVENT_TEMPLATES)
        t = random.choice(templates)
        q = t.format(event=e, event_lc=e[0].lower() + e[1:])
        return _mk(q, "Event Impact", random.choice(["Event", "News"]))

    _fill(records, one, 200)


# ─────────────────────────────────────────────────────────────────────────
# 5. Macro Economy (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_macro_economy(records: list[dict]) -> None:
    templates = [
        "What is the impact of {topic} on the stock market?",
        "How does {topic} affect my investments?",
        "Should I be worried about {topic}?",
        "How should investors respond to {topic}?",
        "What sectors are most affected by {topic}?",
        "Is {topic} a near-term or structural risk?",
        "How does {topic} affect interest rates?",
        "What does {topic} mean for the rupee?",
        "Explain {topic} and its market impact",
        "How is {topic} likely to evolve over the next year?",
    ]

    def one():
        m = random.choice(MACRO_TOPICS)
        t = random.choice(templates)
        q = t.format(topic=m)
        return _mk(q, "Macro Economy", "Macro")

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 6. Government Policy (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_government_policy(records: list[dict]) -> None:
    templates = [
        "What is {policy} and how does it affect investors?",
        "Which companies benefit from {policy}?",
        "Which stocks are hurt by {policy}?",
        "How will {policy} play out for the sector?",
        "Is {policy} good for the economy?",
        "What's the market reaction to {policy}?",
        "How should I position my portfolio around {policy}?",
        "Long-term implications of {policy}",
        "Which sectors gain the most from {policy}?",
    ]

    def one():
        p = random.choice(POLICY_TOPICS)
        t = random.choice(templates)
        q = t.format(policy=p)
        return _mk(q, "Government Policy", "Policy")

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 7. Earnings (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_earnings(records: list[dict]) -> None:
    templates = [
        "{name} {scenario} — what should I do?",
        "{name} {scenario} this quarter, is it a buy?",
        "What does it mean when {name} {scenario}?",
        "{name} just {scenario} — stock reaction?",
        "Should I sell {name} after it {scenario}?",
        "Is {name}'s earnings quality good after it {scenario}?",
        "{sym} {scenario} — how should investors react?",
    ]

    def one():
        c = random.choice(COMPANIES)
        s = random.choice(EARNINGS_SCENARIOS)
        t = random.choice(templates)
        q = t.format(name=c[1], sym=c[0], scenario=s)
        return _mk(q, "Earnings", random.choice(["Company", "News"]))

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 8. IPO (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_ipo(records: list[dict]) -> None:
    templates = [
        "Should I apply for the {name} IPO?",
        "{name} IPO — GMP analysis",
        "Is the {name} IPO worth applying for?",
        "What are the listing gain expectations for {name}?",
        "Is {name} a good long-term investment after listing?",
        "{name} IPO subscription data — what does it signal?",
        "What are the risks in the {name} IPO?",
        "{name} IPO valuation — is it expensive?",
        "Should I sell {name} on listing day or hold?",
        "What is the grey market premium for {name} telling us?",
    ]

    def one():
        n = random.choice(IPO_NAMES)
        t = random.choice(templates)
        q = t.format(name=n)
        return _mk(q, "IPO", "Company")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 9. Market Strategy (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_market_strategy(records: list[dict]) -> None:
    amounts = ["₹10,000", "₹25,000", "₹50,000", "₹1 lakh", "₹2 lakh", "₹5 lakh", "₹10 lakh"]
    templates_portfolio_amt = [
        "Where should I invest {amount} right now?",
        "Best low-risk portfolio for a beginner with {amount}",
        "How should I split {amount} across sectors?",
        "What's the best way to deploy {amount} in this market?",
        "Should I invest {amount} as a lump sum or via SIP?",
    ]
    templates_portfolio_static = [
        "Best defensive portfolio for a volatile market",
        "How should I build a dividend investing portfolio?",
        "What's a good asset allocation for a 30-year-old investor?",
        "How should I rebalance my portfolio this year?",
        "Best portfolio mix for a retiree",
        "How much should I allocate to equity vs debt?",
        "How should a beginner structure their first portfolio?",
        "What's a good portfolio mix for someone nearing retirement?",
    ]
    templates_strategy_static = [
        "Best stocks for a recession",
        "Swing trading ideas for this week",
        "Best stocks to buy for the next Diwali rally",
        "Which stocks to buy before the budget?",
        "Best momentum stocks right now",
        "Contrarian stock picks for this market",
        "Best stocks for a falling interest rate environment",
        "How should traders position for high volatility?",
        "What's a good options strategy for range-bound markets",
        "Best stocks to accumulate on dips",
    ]
    templates_strategy_sector = [
        "Best {sector} stocks for a recession-proof portfolio",
        "Swing trading ideas in the {sector} sector this week",
        "Best {sector} stocks to accumulate on dips",
        "Contrarian {sector} stock picks for this market",
        "Best {sector} momentum stocks right now",
    ]
    templates_strategy_company = [
        "Is {name} a good swing trade this week?",
        "Should I average down on {name}?",
        "Is {name} a good dip-buying opportunity?",
        "What's a good entry strategy for {name}?",
        "Should I use options to hedge my {name} position?",
    ]

    def one():
        roll = random.random()
        if roll < 0.25:
            t = random.choice(templates_portfolio_amt)
            return _mk(t.format(amount=random.choice(amounts)), "Market Strategy", "Portfolio")
        if roll < 0.40:
            return _mk(random.choice(templates_portfolio_static), "Market Strategy", "Portfolio")
        if roll < 0.55:
            return _mk(random.choice(templates_strategy_static), "Market Strategy", "Strategy")
        if roll < 0.80:
            s = random.choice(SECTOR_NAMES)
            t = random.choice(templates_strategy_sector)
            return _mk(t.format(sector=s), "Market Strategy", "Strategy")
        c = random.choice(COMPANIES)
        t = random.choice(templates_strategy_company)
        return _mk(t.format(name=c[1]), "Market Strategy", "Strategy")

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 10. Historical Events (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_historical_events(records: list[dict]) -> None:
    templates = [
        "What happened to the market during {event}?",
        "How did stocks recover after {event}?",
        "What lessons does {event} offer for today's market?",
        "Which sectors outperformed during {event}?",
        "Which sectors were hit hardest by {event}?",
        "How similar is today's market to {event}?",
        "How long did it take markets to recover from {event}?",
        "What should investors learn from {event}?",
    ]

    def one():
        e = random.choice(HISTORICAL_EVENTS)
        t = random.choice(templates)
        q = t.format(event=e)
        return _mk(q, "Historical Events", "Event")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 11. Theme Investing (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_theme_investing(records: list[dict]) -> None:
    templates = [
        "Best {theme} stocks to invest in",
        "Is the {theme} theme still investable?",
        "How do I get exposure to the {theme} theme in India?",
        "Which stocks lead the {theme} theme?",
        "Is the {theme} theme overhyped?",
        "What's the long-term potential of the {theme} theme?",
        "Best way to play the {theme} theme for the next 5 years",
        "Which small caps benefit from the {theme} theme?",
    ]

    def one():
        th = random.choice(THEMES)
        t = random.choice(templates)
        q = t.format(theme=th)
        return _mk(q, "Theme Investing", "Theme")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 12. Commodities (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_commodities(records: list[dict]) -> None:
    templates = [
        "What's the outlook for {commodity} prices?",
        "How does rising {commodity} affect Indian stocks?",
        "Which companies benefit from falling {commodity} prices?",
        "Should I invest in {commodity} right now?",
        "Why is {commodity} rallying?",
        "Why is {commodity} falling?",
        "What's driving {commodity} prices globally?",
        "How does {commodity} affect India's import bill?",
    ]

    def one():
        c = random.choice(COMMODITIES)
        t = random.choice(templates)
        q = t.format(commodity=c)
        return _mk(q, "Commodities", "Macro")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 13. Global Markets (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_global_markets(records: list[dict]) -> None:
    templates = [
        "How does {event} affect Indian markets?",
        "What's the impact of {event} on IT stocks?",
        "What's the impact of {event} on FII flows?",
        "Should Indian investors worry about {event}?",
        "How should I position my portfolio for {event}?",
        "What does {event} mean for emerging markets?",
        "How correlated are Indian markets with {event}?",
    ]

    def one():
        e = random.choice(GLOBAL_EVENTS)
        t = random.choice(templates)
        q = t.format(event=e)
        return _mk(q, "Global Markets", "Macro")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 14. Risk Management (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_risk_management(records: list[dict]) -> None:
    templates = [
        "How should I think about {topic}?",
        "What's the best approach to {topic} in a volatile market?",
        "Explain {topic} with a practical example",
        "How do professional traders approach {topic}?",
        "What mistakes do investors make with {topic}?",
        "How does {topic} change in a bear market?",
        "How does {topic} change in a bull market?",
        "What's a beginner's guide to {topic}?",
        "How do fund managers handle {topic}?",
        "What's the biggest myth about {topic}?",
    ]

    def one():
        r = random.choice(RISK_TOPICS)
        t = random.choice(templates)
        q = t.format(topic=r)
        return _mk(q, "Risk Management", "Risk")

    _fill(records, one, 100)


# ─────────────────────────────────────────────────────────────────────────
# 15. Beginner Questions (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_beginner(records: list[dict]) -> None:
    templates = [
        "What is {term}?",
        "Explain {term} in simple terms",
        "Why does {term} matter for investors?",
        "How do I use {term} to pick stocks?",
        "What is a good {term} for a stock?",
        "Can you explain {term} like I'm new to investing?",
    ]

    def one():
        term = random.choice(BEGINNER_TERMS)
        t = random.choice(templates)
        q = t.format(term=term)
        return _mk(q, "Beginner Questions", "Education", difficulty="Easy", persona="Beginner")

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 16. Advanced Investor Questions (150)
# ─────────────────────────────────────────────────────────────────────────
def gen_advanced(records: list[dict]) -> None:
    templates = [
        "Walk me through {term} for {name}",
        "How do I calculate {term} for {name}?",
        "What does {term} tell us about {name}'s quality?",
        "Is {name}'s {term} sustainable?",
        "How does {name} compare on {term} to its peers?",
        "Explain {term} with {name} as an example",
    ]

    def one():
        term = random.choice(ADVANCED_TERMS)
        c = random.choice(COMPANIES)
        t = random.choice(templates)
        q = t.format(term=term, name=c[1])
        return _mk(q, "Advanced Investor Questions", "Education", difficulty="Expert",
                    persona=random.choice(["Fund Manager", "Value Investor", "Financial Advisor", "Growth Investor"]))

    _fill(records, one, 150)


# ─────────────────────────────────────────────────────────────────────────
# 17. AI Search Edge Cases (100)
# ─────────────────────────────────────────────────────────────────────────
def gen_edge_cases(records: list[dict]) -> None:
    misspellings = [
        "Relaince", "Infosis", "TCS ltd", "HDFC bnk", "ICICI Bnk", "Adnai",
        "Bajaj Fin", "Suzlonn", "Zomatoo", "Nykka", "Maruthi Suzuki",
        "Bharti Airtell", "Wiproo", "SBI bank", "Asian Paint",
    ]
    one_word = [
        "Reliance", "Undervalued?", "Sell?", "Overvalued?", "TCS", "Crash?",
        "Recession?", "Inflation?", "IPO?", "Rally?", "Defence", "Gold?",
        "HAL", "Rebound?", "Correction?",
    ]
    hinglish = [
        "Reliance ka stock kaisa hai?", "TCS mein invest karna chahiye?",
        "Kya HDFC Bank abhi sasta hai?", "Market crash hoga kya?",
        "RBI rate cut ka kya asar hoga stocks pe?", "Best stock for long term batao",
        "Kal market kaisa rahega?", "Defence stocks ka future kaisa hai?",
        "Kya ye sahi time hai IPO apply karne ka?", "Gold mein paisa lagana chahiye ya nahi?",
    ]

    def multi_company():
        cs = random.sample(COMPANIES, random.choice([3, 4]))
        return f"Compare {', '.join(c[1] for c in cs[:-1])} and {cs[-1][1]}"

    def multi_event():
        es = random.sample(EVENT_TEMPLATES, 2)
        return f"What happens if {es[0][0].lower() + es[0][1:]} and {es[1][0].lower() + es[1][1:]} at the same time?"

    def ambiguous():
        return random.choice([
            "Should I sell?", "Is it a good time?", "What should I do now?",
            "Is this stock safe?", "Will it go up?", "Should I buy more?",
            "Is the market going to crash?", "What's happening?",
            "Is it too late to invest?", "Should I panic?",
        ])

    generators = [
        lambda: _mk(random.choice(misspellings), "AI Search Edge Cases", "Company", difficulty="Hard"),
        lambda: _mk(random.choice(one_word), "AI Search Edge Cases", "Company", difficulty="Hard"),
        lambda: _mk(random.choice(hinglish), "AI Search Edge Cases", "Company", difficulty="Hard"),
        lambda: _mk(multi_company(), "AI Search Edge Cases", "Comparison", difficulty="Expert"),
        lambda: _mk(multi_event(), "AI Search Edge Cases", "Event", difficulty="Expert"),
        lambda: _mk(ambiguous(), "AI Search Edge Cases", "Company", difficulty="Hard"),
    ]

    def one():
        return random.choice(generators)()

    _fill(records, one, 100)


CATEGORY_GENERATORS = [
    gen_company_analysis, gen_company_comparison, gen_sector_analysis,
    gen_event_impact, gen_macro_economy, gen_government_policy, gen_earnings,
    gen_ipo, gen_market_strategy, gen_historical_events, gen_theme_investing,
    gen_commodities, gen_global_markets, gen_risk_management, gen_beginner,
    gen_advanced, gen_edge_cases,
]


def build_dataset() -> list[dict]:
    records: list[dict] = []
    for gen in CATEGORY_GENERATORS:
        gen(records)
    return records


def pick_golden(records: list[dict], target: int = 200) -> list[dict]:
    """Curate a diverse mission-critical subset: proportional per-category
    sampling (so no category dominates) plus a handful of hand-specified
    must-include questions from the product spec, if present in the pool."""
    must_include_text = {
        _norm(q) for q in [
            "HAL vs BEL",
            "Is Reliance overvalued?",
            "Should I buy TCS after earnings?",
        ]
    }
    by_category: dict[str, list[dict]] = {}
    for r in records:
        by_category.setdefault(r["category"], []).append(r)

    golden: list[dict] = []
    golden_ids: set[str] = set()

    # 1) explicit must-includes
    for r in records:
        if _norm(r["question"]) in must_include_text and r["id"] not in golden_ids:
            golden.append(r)
            golden_ids.add(r["id"])

    # 2) proportional sampling per category, weighted toward Easy/Medium
    #    (broad usefulness) with some Hard/Expert for real stress-testing
    n_categories = len(by_category)
    per_category = max(1, target // n_categories)
    for cat, items in by_category.items():
        pool = [r for r in items if r["id"] not in golden_ids]
        random.shuffle(pool)
        pool.sort(key=lambda r: {"Easy": 0, "Medium": 1, "Hard": 2, "Expert": 3}[r["difficulty"]])
        for r in pool[:per_category]:
            if r["id"] not in golden_ids:
                golden.append(r)
                golden_ids.add(r["id"])

    # 3) top up to target from the general pool if short
    remaining = [r for r in records if r["id"] not in golden_ids]
    random.shuffle(remaining)
    while len(golden) < target and remaining:
        r = remaining.pop()
        golden.append(r)
        golden_ids.add(r["id"])

    return golden[:target] if len(golden) > target else golden


EVAL_COLUMNS = [
    "id", "question", "category", "difficulty", "intent", "persona", "time_horizon",
    "Answered Correctly?", "Verdict Clear?", "Reasoning Quality (1-10)",
    "Evidence Quality (1-10)", "Company Detection", "Event Detection",
    "Historical Match", "Relevant Sources", "Investment Conclusion",
    "Confidence Appropriate", "Hallucination", "Response Time", "UI Issues", "Notes",
    # UI/UX scoring — AI Search is a product, not just an API. All 1-5 stars,
    # human-scored (screen-reading judgment, not automatable from JSON).
    "AI Verdict Visible (1-5)", "Executive Summary Quality (1-5)",
    "Ripple Graph Quality (1-5)", "Comparison Quality (1-5)",
    "Sources Relevance (1-5)", "Recommendation Usefulness (1-5)",
    "Overall UX (1-5)",
]


def write_evaluation_sheet(records: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EVAL_COLUMNS)
        writer.writeheader()
        for r in records:
            row = {k: "" for k in EVAL_COLUMNS}
            row.update({
                "id": r["id"], "question": r["question"], "category": r["category"],
                "difficulty": r["difficulty"], "intent": r["intent"],
                "persona": r["persona"], "time_horizon": r["time_horizon"],
            })
            writer.writerow(row)


def main() -> None:
    records = build_dataset()

    by_category: dict[str, int] = {}
    for r in records:
        by_category[r["category"]] = by_category.get(r["category"], 0) + 1

    print(f"Generated {len(records)} unique questions across {len(by_category)} categories:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat:32s} {count}")

    dataset_path = OUT_DIR / "dataset.json"
    dataset_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {dataset_path} ({len(records)} records)")

    golden = pick_golden(records, target=200)
    golden_path = OUT_DIR / "golden_questions.json"
    golden_path.write_text(json.dumps(golden, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {golden_path} ({len(golden)} records)")

    eval_path = OUT_DIR / "evaluation_sheet.csv"
    write_evaluation_sheet(records, eval_path)
    print(f"Wrote {eval_path} ({len(records)} rows)")

    # Sanity: zero duplicate question text across the full dataset
    norm_texts = [_norm(r["question"]) for r in records]
    assert len(norm_texts) == len(set(norm_texts)), "duplicate questions found!"
    print("\nDuplicate check: PASSED (0 duplicates)")


if __name__ == "__main__":
    main()

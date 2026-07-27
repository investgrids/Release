"""
Generates expected_answers.json — ground-truth regression checks for AI
Search.

Honesty boundary (read before extending this file): this script asserts
`winner` only where it's a stable, checkable *structural* fact (e.g. which
company actually manufactures a named product) — never a forward-looking
"which stock performs better" call. Real investment-comparison winners
need a domain expert's actual judgment or backtested data; fabricating them
here would bake hallucinated advice into a suite meant to catch
hallucinations. Comparison entries instead check what's objectively
verifiable from any response — did it correctly identify both companies,
did it engage with the right analytical themes for that sector — and flag
`winner_needs_review: true` so a human can fill in a real call later.

Run:
    python generate_expected_answers.py
"""
from __future__ import annotations

import json
from pathlib import Path

from data import COMPANIES

OUT_DIR = Path(__file__).parent
_next_id = 1

SYM_TO_SECTOR = {c[0]: c[2] for c in COMPANIES}
NAME_TO_SYM = {c[1]: c[0] for c in COMPANIES}

# ─────────────────────────────────────────────────────────────────────────
# Sector-appropriate analytical themes — what a *competent* answer should
# engage with, regardless of which company it favors. Checkable without
# asserting a directional call.
# ─────────────────────────────────────────────────────────────────────────
SECTOR_THEMES: dict[str, list[str]] = {
    "Banking":     ["asset quality", "net interest margin", "credit growth", "provisioning"],
    "NBFC":        ["asset quality", "cost of funds", "loan growth", "AUM"],
    "Insurance":   ["premium growth", "claims ratio", "persistency", "embedded value"],
    "IT":          ["margins", "deal wins", "attrition", "revenue growth"],
    "Auto":        ["volume growth", "margins", "EV transition", "input costs"],
    "Pharma":      ["US generics", "regulatory approvals", "R&D spend", "pipeline"],
    "Healthcare":  ["occupancy", "ARPOB", "capacity expansion"],
    "FMCG":        ["rural demand", "volume growth", "input costs", "market share"],
    "Consumer":    ["premiumisation", "margins", "distribution reach"],
    "Electronics": ["order book", "PLI benefits", "capacity expansion"],
    "Defence":     ["order book", "government spending", "export orders", "execution timelines"],
    "New-age":     ["path to profitability", "unit economics", "customer growth"],
    "Retail":      ["same-store sales growth", "store expansion", "margins"],
    "Aviation":    ["load factor", "fuel costs", "yields"],
    "Travel":      ["ticketing volumes", "margins"],
    "Metals":      ["realisations", "input costs", "capacity utilisation"],
    "Mining":      ["production volumes", "e-auction premiums"],
    "Power":       ["capacity addition", "plant load factor", "tariffs"],
    "Infra":       ["order book", "execution pace", "working capital"],
    "Cement":      ["realisations", "volume growth", "input costs"],
    "Realty":      ["pre-sales", "launch pipeline", "collections"],
    "Telecom":     ["ARPU", "subscriber additions", "capex"],
    "Media":       ["ad revenue", "subscriber growth", "content costs"],
    "Exchange":    ["volume growth", "market share", "yields"],
    "Broking":     ["client additions", "active clients", "yields"],
    "Fintech":     ["client additions", "revenue per client"],
    "Chemicals":   ["realisations", "capacity expansion", "export demand"],
    "Energy":      ["refining margins", "crude prices", "throughput"],
    "Logistics":   ["volume growth", "yields", "network expansion"],
    "Exchange": ["volume growth", "market share"],
}
DEFAULT_THEMES = ["valuation", "growth outlook", "margins"]


def _themes_for(sym: str) -> list[str]:
    sector = SYM_TO_SECTOR.get(sym, "")
    return SECTOR_THEMES.get(sector, DEFAULT_THEMES)[:3]


def _mk(question: str, expected: dict) -> dict:
    global _next_id
    rec = {"id": f"ea{_next_id:05d}", "question": question, "expected": expected}
    _next_id += 1
    return rec


# ─────────────────────────────────────────────────────────────────────────
# 1. Factual questions — real, stable, structural facts only. No market
#    data (prices, "largest by market cap", etc.) since those aren't stable.
# ─────────────────────────────────────────────────────────────────────────
FACTUAL = [
    ("Who manufactures the Tejas fighter aircraft?", "HAL",
     ["Tejas", "HAL"], ["BEL"]),
    ("Which company manufactures the Dhruv helicopter?", "HAL",
     ["Dhruv", "HAL"], []),
    ("Which company is India's largest IT services exporter by employee count?", "TCS",
     ["TCS"], []),
    ("What is the parent group of TCS?", "TCS",
     ["Tata"], []),
    ("What is the parent group of Tata Motors?", "TATAMOTORS",
     ["Tata"], []),
    ("Which company owns Jaguar Land Rover?", "TATAMOTORS",
     ["Tata Motors", "Jaguar Land Rover"], []),
    ("Which company operates the Zomato food delivery app?", "ZOMATO",
     ["Eternal", "Zomato"], []),
    ("What is the current corporate name of the company that runs Zomato?", "ZOMATO",
     ["Eternal"], []),
    ("Which company manufactures Maruti-badged cars in India?", "MARUTI",
     ["Maruti Suzuki"], []),
    ("Which company runs the DMart retail chain?", "DMART",
     ["Avenue Supermarts", "DMart"], []),
    ("Which company operates IndiGo airlines?", "INDIGO",
     ["InterGlobe Aviation", "IndiGo"], []),
    ("Which company runs the IRCTC ticketing platform?", "IRCTC",
     ["IRCTC", "Indian Railway"], []),
    ("Which bank is promoted by the Kotak group?", "KOTAKBANK",
     ["Kotak Mahindra Bank"], []),
    ("Which company manufactures Bajaj-badged motorcycles?", "BAJAJ-AUTO",
     ["Bajaj Auto"], []),
    ("Which company owns the Titan watch and jewellery brand Tanishq?", "TITAN",
     ["Titan", "Tanishq"], []),
    ("Which company operates the BigBasket-style DMart retail format?", "DMART",
     ["DMart", "Avenue Supermarts"], []),
    ("Which oil marketing company operates under the brand name Indane?", "IOC",
     ["Indian Oil", "Indane"], []),
    ("Which company runs the Airtel telecom network?", "BHARTIARTL",
     ["Bharti Airtel"], []),
    ("Which company is the listed entity for Nestle's India operations?", "NESTLEIND",
     ["Nestle India"], []),
    ("Which company manufactures shipbuilding vessels for the Indian Navy at Mazagon Dock?", "MAZDOCK",
     ["Mazagon Dock"], []),
]

# ─────────────────────────────────────────────────────────────────────────
# 2. Hallucination traps — company names that do not exist. The correct
#    response is to say so, not invent financials for a fictional entity.
# ─────────────────────────────────────────────────────────────────────────
FAKE_COMPANIES = [
    "Apple India Defence Ltd", "Bharat Quantum Computing Ltd", "Reliance Space Systems",
    "Tata Neuralink", "Adani Lunar Mining Corp", "HDFC Metaverse Bank",
    "Infosys Nuclear Energy Ltd", "Vedanta Interstellar Ltd", "SBI Crypto Holdings",
    "ITC Robotics Division Ltd", "Maruti Hyperloop Ltd", "Sun Pharma Genomics International",
    "Wipro Asteroid Mining", "L&T Antarctica Infrastructure", "Zomato Aerospace Ltd",
    "Bajaj Fusion Energy Corp", "Titan Deep Sea Exploration", "HAL Commercial Airlines Retail",
    "BEL Consumer Electronics Ltd", "Coal India Solar Devision",
]
FAKE_TEMPLATES = [
    "Analyze {name}",
    "Is {name} overvalued?",
    "Should I buy {name}?",
    "Compare {name} vs {real}",
    "What is the outlook for {name}?",
    "{name} vs {real} — which is the better buy?",
]


def gen_factual(records: list[dict]) -> None:
    for question, sym, must_mention, must_not in FACTUAL:
        records.append(_mk(question, {
            "query_type": "factual",
            "companies": [sym],
            "winner": sym,
            "winner_needs_review": False,
            # No confidence_min here on purpose: the system's confidence
            # score measures investment-thesis confidence, not factual
            # certainty — a purely factual question (verified live: "who
            # manufactures Tejas" answered correctly with HAL) can
            # legitimately score low on that axis despite being 100%
            # correct. Correctness for factual entries rides entirely on
            # must_mention/must_not_mention, not confidence.
            "confidence_min": None,
            "must_mention": must_mention,
            "must_not_mention": must_not,
            "expected_behavior": "normal",
        }))


def gen_hallucination_traps(records: list[dict]) -> None:
    import random
    random.seed(20260725)
    for i, name in enumerate(FAKE_COMPANIES):
        t = FAKE_TEMPLATES[i % len(FAKE_TEMPLATES)]
        real = random.choice(COMPANIES)[1] if "{real}" in t else None
        q = t.format(name=name, real=real) if real else t.format(name=name)
        records.append(_mk(q, {
            "query_type": "hallucination_trap",
            "companies": [],
            "winner": None,
            "winner_needs_review": False,
            "confidence_min": None,
            "must_mention": ["no verified", "not found", "unable to identify", "no matching company", "couldn't find", "no record"],
            "must_mention_match_mode": "any",
            "must_not_mention": [],
            "expected_behavior": "reject_unknown_entity",
        }))


def gen_comparisons(records: list[dict], dataset: list[dict]) -> None:
    """Reuse the actual Company Comparison questions already in
    dataset.json — expected_answers should check real benchmark questions,
    not a disconnected parallel set."""
    import re
    seen = 0
    for q in dataset:
        if q["category"] != "Company Comparison" or seen >= 80:
            continue
        text = q["question"]
        # Match against known company names/symbols mentioned in the text
        hits = [sym for name, sym in NAME_TO_SYM.items() if name in text]
        hits += [c[0] for c in COMPANIES if re.search(r"\b" + re.escape(c[0]) + r"\b", text)]
        hits = list(dict.fromkeys(hits))[:2]
        if len(hits) < 2:
            continue
        themes = list(dict.fromkeys(_themes_for(hits[0]) + _themes_for(hits[1])))[:4]
        records.append({
            "id": f"ea_cmp_{q['id']}",
            "question": text,
            "dataset_id": q["id"],
            "expected": {
                "query_type": "comparison",
                "companies": hits,
                "winner": None,
                "winner_needs_review": True,
                "confidence_min": 30,
                "must_mention": themes,
                "must_not_mention": [],
                "expected_behavior": "normal",
            },
        })
        seen += 1


def gen_company_analysis(records: list[dict], dataset: list[dict]) -> None:
    import re
    seen = 0
    for q in dataset:
        if q["category"] != "Company Analysis" or seen >= 60:
            continue
        text = q["question"]
        hits = [c[0] for c in COMPANIES if c[1] in text or re.search(r"\b" + re.escape(c[0]) + r"\b", text)]
        if not hits:
            continue
        sym = hits[0]
        records.append({
            "id": f"ea_co_{q['id']}",
            "question": text,
            "dataset_id": q["id"],
            "expected": {
                "query_type": "company_analysis",
                "companies": [sym],
                "winner": None,
                "winner_needs_review": False,
                "confidence_min": 30,
                "must_mention": _themes_for(sym),
                "must_not_mention": [],
                "expected_behavior": "normal",
            },
        })
        seen += 1


def main() -> None:
    records: list[dict] = []
    gen_factual(records)
    gen_hallucination_traps(records)

    dataset_path = OUT_DIR / "dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8")) if dataset_path.exists() else []
    if dataset:
        gen_comparisons(records, dataset)
        gen_company_analysis(records, dataset)

    by_type: dict[str, int] = {}
    for r in records:
        t = r["expected"]["query_type"]
        by_type[t] = by_type.get(t, 0) + 1

    print(f"Generated {len(records)} expected-answer records:")
    for t, c in sorted(by_type.items()):
        print(f"  {t:20s} {c}")
    needs_review = sum(1 for r in records if r["expected"].get("winner_needs_review"))
    print(f"\n  {needs_review} comparison entries flagged winner_needs_review=true "
          f"(no fabricated investment-winner calls)")

    out_path = OUT_DIR / "expected_answers.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()

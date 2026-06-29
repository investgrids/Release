"""
Event classifier â€” maps raw text to sector, category, and company symbols.
Uses keyword heuristics as primary path; falls back to AI when key is set.
"""
from __future__ import annotations

import structlog
import re
from typing import Any

import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)

# â”€â”€ Sector keyword map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Infrastructure": ["infrastructure", "capex", "roads", "highways", "ports", "airport", "metro", "data center"],
    "Railways":       ["railway", "rail", "ircon", "rvnl", "kavach", "vande bharat", "freight corridor"],
    "Energy":         ["solar", "wind", "renewable", "hydrogen", "power", "ntpc", "energy", "electricity"],
    "Defence":        ["defence", "defense", "hal", "bel", "drdo", "military", "weapon", "missile"],
    "Technology":     ["ai", "artificial intelligence", "tech", "software", "it ", "digital", "semiconductor"],
    "Banking":        ["bank", "rbi", "credit", "npa", "repo rate", "fintech", "nbfc", "insurance"],
    "Pharma":         ["pharma", "drug", "medicine", "health", "hospital", "biotech", "fda"],
    "Automotive":     ["ev", "electric vehicle", "auto", "car", "maruti", "tata motors", "electric mobility"],
    "FMCG":           ["fmcg", "consumer", "food", "beverage", "hul", "itc", "godrej"],
    "Metals":         ["steel", "aluminium", "copper", "zinc", "metal", "mining"],
    "Manufacturing":  ["pli", "manufacturing", "production", "factory", "make in india"],
    "Real Estate":    ["real estate", "housing", "realty", "construction", "reit"],
}

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Government":    ["budget", "government", "ministry", "scheme", "policy", "allocation", "announcement"],
    "Corporate":     ["results", "earnings", "profit", "revenue", "order win", "merger", "acquisition", "ipo"],
    "Policy":        ["sebi", "rbi", "regulation", "circular", "guideline", "reform", "compliance"],
    "Infrastructure":["project", "tender", "contract", "bid", "capacity", "plant", "expansion"],
    "Global":        ["us", "fed", "global", "china", "europe", "crude", "dollar", "import", "export"],
}

# NSE symbol â†’ company name
_COMPANY_MAP: dict[str, list[str]] = {
    "RELIANCE":   ["reliance"],
    "TCS":        ["tata consultancy", " tcs "],
    "HDFCBANK":   ["hdfc bank", "hdfc"],
    "INFY":       ["infosys"],
    "LT":         ["larsen", "l&t"],
    "NTPC":       ["ntpc"],
    "ONGC":       ["ongc"],
    "SBIN":       ["sbi", "state bank"],
    "ICICIBANK":  ["icici bank", "icici"],
    "KOTAKBANK":  ["kotak"],
    "AXISBANK":   ["axis bank"],
    "TATASTEEL":  ["tata steel"],
    "TATAMOTORS": ["tata motors"],
    "WIPRO":      ["wipro"],
    "HCLTECH":    ["hcl tech", "hcltech"],
    "BAJFINANCE": ["bajaj finance"],
    "MARUTI":     ["maruti"],
    "BEL":        ["bharat electronics", " bel "],
    "HAL":        ["hindustan aeronautics", " hal "],
    "RVNL":       ["rvnl", "rail vikas"],
    "IRCON":      ["ircon"],
    "BEML":       ["beml"],
    "ADANIENT":   ["adani"],
    "SUNPHARMA":  ["sun pharma"],
    "ZOMATO":     ["zomato"],
    "AIRTEL":     ["airtel", "bharti"],
}


def classify_text(text: str) -> dict[str, Any]:
    """
    Keyword-based classification.
    Returns: {sectors, category, companies, confidence}
    """
    lower = (" " + text.lower() + " ")
    sectors: list[str] = []
    category = "General"
    companies: list[str] = []

    for sector, keywords in _SECTOR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            sectors.append(sector)

    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            category = cat
            break

    for symbol, aliases in _COMPANY_MAP.items():
        if any(alias in lower for alias in aliases):
            companies.append(symbol)

    confidence = min(0.95, 0.6 + len(sectors) * 0.05 + len(companies) * 0.04)

    return {
        "sectors": sectors[:3],
        "category": category,
        "companies": companies[:8],
        "confidence": round(confidence, 2),
    }


async def classify_with_ai(text: str) -> dict[str, Any]:
    """
    AI-powered classification via DeepSeek.
    Falls back to keyword classifier if key is absent or request fails.
    """
    if not settings.deepseek_api_key:
        return classify_text(text)

    prompt = f"""Classify this Indian market news/event. Return ONLY valid JSON.

TEXT: {text[:800]}

Return JSON:
{{
  "sectors": ["<sector1>", "<sector2>"],
  "category": "<Government|Corporate|Policy|Infrastructure|Global>",
  "companies": ["<NSE_SYMBOL1>", "<NSE_SYMBOL2>"],
  "confidence": <0.0-1.0>
}}"""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Extract JSON block
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                import json
                return json.loads(match.group())
    except Exception as exc:
        logger.warning("AI classifier failed: %s â€” falling back to keywords", exc)

    return classify_text(text)


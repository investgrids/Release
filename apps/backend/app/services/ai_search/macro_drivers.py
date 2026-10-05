"""
Macro-driver questions (Step 4A): "How would higher crude oil prices affect Indian markets?", "How would a weaker rupee affect Indian IT exporters?".

These ask how a macro condition transmits to markets or a sector. Before this module the only way a question became `policy_macro_impact` was a resolved POLICY entity (RBI, repo rate, budget), so a commodity or
currency driver fell through to direct_company_research, and a sector question without the literal word "sector" (MP3) was routed to the company specialist even though its sector was resolved.

Deterministic and conservative: a question is a macro-driver question only when it names a driver in the table below AND asks how it affects something (an impact verb). Educational questions that merely mention a
driver ("What is crude oil?", "What does FII selling mean ...") do not match. Callers additionally require that no company is resolved: a company question stays a company question.
"""
from __future__ import annotations

import re

# driver label -> pattern. Extend by adding a row; keep patterns specific (no bare "oil" or "dollar").
_DRIVERS: dict[str, re.Pattern] = {
    "crude_oil": re.compile(r"(?<![a-z])(?:crude(?:\s+oil)?|brent|oil\s+prices?|price\s+of\s+(?:crude|oil))(?![a-z])", re.IGNORECASE),
    "fx_rupee": re.compile(
        r"(?<![a-z])(?:rupee|usd\s*/?\s*inr|usdinr|inr\s+(?:depreciat|weaken|fall)\w*|(?:strong(?:er)?|rising|higher)\s+(?:us\s+)?dollar|dollar\s+index)(?![a-z])", re.IGNORECASE),
}

# The question must ask for an effect, not just mention the driver.
_IMPACT = re.compile(
    r"(?<![a-z])(?:affect|impact|effect|influence|hurt|hit|help|benefit|pressure|squeeze|boost|lift)\w*(?![a-z])|(?<![a-z])what\s+happens\s+(?:to|if)(?![a-z])",
    re.IGNORECASE,
)


# "Which sectors benefit from lower crude prices?" asks the system to DISCOVER sectors (sector-theme research), not how a driver transmits to a named market or sector.
_DISCOVERY = re.compile(r"(?<![a-z])(?:which|what|best|top)\s+(?:[a-z-]+\s+){0,2}(?:sectors|industries)(?![a-z])", re.IGNORECASE)


def macro_driver(query: str) -> str | None:
    """The driver label when the query asks how a named macro driver affects something, else None."""
    q = query or ""
    if not _IMPACT.search(q) or _DISCOVERY.search(q):
        return None
    for label, pattern in _DRIVERS.items():
        if pattern.search(q):
            return label
    return None

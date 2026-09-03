"""
Re-run of the EXACT v3 resolver logic (b5_entity_resolver.py, unchanged
rules), but against today's current RawEvidence corpus and using the
fast combined-pattern scan instead of the original's per-identifier
regex compile (which turned out to be the real cause of a multi-minute
hang on this larger identifier set -- see b5_entity_resolver_v4.py's
_build_combined_pattern docstring). This exists ONLY to produce a fair,
same-corpus "before" baseline for the v4 before/after comparison -- the
corpus grew from 594 to 630 real RSS rows between the original v3
benchmark run and this session (continued local ingestion in this
worktree), so re-running v3's real logic against today's 630-row corpus
is the only way to isolate "what changed because of the algorithm" from
"what changed because the corpus grew."
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.raw_evidence import RawEvidence

_LEGAL_SUFFIXES = re.compile(
    r"\s+(limited|ltd\.?|private limited|pvt\.? ltd\.?|corporation|corp\.?|inc\.?|plc|llp|company)\s*$",
    re.IGNORECASE,
)
_STOPLIST = {
    "it", "on", "go", "up", "in", "at", "as", "is", "or", "to", "of", "gold",
    "idea", "info", "star", "route", "team", "wealth", "prime", "shine",
    "focus", "spark", "orbit", "pace", "trend", "vision", "value", "action",
    "asset", "credit", "capital", "finance", "future", "global", "growth",
    "india", "national", "united", "power", "energy", "steel", "bank",
    "industries", "international", "systems", "technologies", "solutions",
    "oil", "dollar", "retail", "worth", "reliance", "shah",
    "bse", "mcx", "nse",
    "take", "total", "race", "shree", "rishabh",
}
_SYMBOL_CASE_SENSITIVE = True


def _strip_suffix(name: str) -> str:
    return _LEGAL_SUFFIXES.sub("", name).strip()


def _build_combined_pattern(idents: list[str], case_sensitive: bool) -> re.Pattern | None:
    if not idents:
        return None
    flags = 0 if case_sensitive else re.IGNORECASE
    ordered = sorted(idents, key=len, reverse=True)
    body = "|".join(re.escape(i) for i in ordered)
    return re.compile(r"(?<![A-Za-z0-9])(" + body + r")(?![A-Za-z0-9])", flags)


async def _load_identifiers():
    async with AsyncSessionLocal() as db:
        entities = (await db.execute(select(CompanyEntity.entity_id, CompanyEntity.company_name, CompanyEntity.symbol))).all()
        aliases = (await db.execute(select(CompanyAlias.entity_id, CompanyAlias.alias_value))).all()

    name_raw: dict[str, set[str]] = defaultdict(set)
    symbol_raw: dict[str, set[str]] = defaultdict(set)
    for entity_id, company_name, symbol in entities:
        core = _strip_suffix(company_name).lower()
        if len(core) >= 4 and core not in _STOPLIST:
            name_raw[core].add(entity_id)
        sym = symbol or ""
        if len(sym) >= 3 and sym.lower() not in _STOPLIST:
            symbol_raw[sym].add(entity_id)
    for entity_id, alias_value in aliases:
        a = (alias_value or "").lower()
        if len(a) >= 3 and a not in _STOPLIST:
            name_raw[a].add(entity_id)

    return name_raw, symbol_raw


async def build_index():
    name_raw, symbol_raw = await _load_identifiers()
    name_index = {ident: next(iter(eids)) for ident, eids in name_raw.items() if len(eids) == 1}
    symbol_index = {ident: next(iter(eids)) for ident, eids in symbol_raw.items() if len(eids) == 1}
    return name_index, symbol_index


def _scan(text, title_len, pattern, index, method, case_sensitive, matches):
    if pattern is None:
        return
    for m in pattern.finditer(text):
        t = m.group(1)
        key = t if case_sensitive else t.lower()
        eid = index.get(key)
        if eid is None or eid in matches:
            continue
        matches[eid] = {"entity_id": eid, "method": method, "matched_text": t, "in_title": m.start() < title_len}


async def main() -> None:
    name_index, symbol_index = await build_index()
    print(f"v3-rerun identifiers: names/aliases={len(name_index)} symbols={len(symbol_index)}")

    name_pattern = _build_combined_pattern(list(name_index.keys()), case_sensitive=False)
    symbol_pattern = _build_combined_pattern(list(symbol_index.keys()), case_sensitive=_SYMBOL_CASE_SENSITIVE)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(RawEvidence.id, RawEvidence.title, RawEvidence.raw_payload)
            .where(RawEvidence.source_type == "rss")
        )).all()

    results = []
    for r in rows:
        try:
            payload = json.loads(r.raw_payload) if r.raw_payload else {}
        except json.JSONDecodeError:
            payload = {}
        title = r.title or ""
        summary = payload.get("summary", "")
        text = f"{title} {summary}"
        matches: dict[str, dict] = {}
        _scan(text, len(title), name_pattern, name_index, "name_or_alias", False, matches)
        _scan(text, len(title), symbol_pattern, symbol_index, "symbol", _SYMBOL_CASE_SENSITIVE, matches)
        results.append({"id": r.id, "title": title, "summary": summary, "matches": list(matches.values())})

    unlinked = [r for r in results if len(r["matches"]) == 0]
    single = [r for r in results if len(r["matches"]) == 1]
    multi = [r for r in results if len(r["matches"]) >= 2]
    print(f"total real RSS items: {len(results)}")
    print(f"  UNLINKED: {len(unlinked)}  SINGLE: {len(single)}  MULTI: {len(multi)}")

    import pickle
    with open("b5_resolver_results_v3_rerun.pkl", "wb") as f:
        pickle.dump(results, f)
    print("pickled to b5_resolver_results_v3_rerun.pkl")


if __name__ == "__main__":
    asyncio.run(main())

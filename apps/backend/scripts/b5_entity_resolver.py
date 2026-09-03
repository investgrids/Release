"""
B.5 design/benchmark (owner-authorized 2026-08-30) -- Gate 1 (entity
linkage) real, deterministic resolver against the real RSS RawEvidence
corpus (594 real rows). NOT wired into production, NOT a mass backfill --
a real implementation used to generate the 100-item labeled benchmark and
measure real precision/recall before any of this is trusted.

Rules implemented, per the owner's exact spec:
  - explicit NSE symbol (whole-word match)
  - exact canonical company name (legal-suffix-stripped, whole-phrase match)
  - exact known alias (CompanyAlias rows -- real, sourced, never fuzzy)
  - multi-company stories allowed (2+ distinct real matches kept, not rejected)
  - ambiguous stays unlinked: a symbol/name/alias string that collides
    across 2+ DIFFERENT real entities is excluded from matching entirely
    (never guessed at), and a stoplist excludes short/common-word symbols
    that would otherwise fire on ordinary prose
  - NO sector-based or fuzzy "probably this company" inference anywhere

Deliberately NOT implemented here (Gate 2, a separate later step): the
event-specific evidence-matching gate. This script only answers "which
real company/companies, if any, does this real RSS item unambiguously
mention" -- it does not yet check whether the Warehouse's own NSE
evidence for that company matches the SAME event.
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

# Real, manually-identified false-positive risks: short/common-word symbols,
# common surnames, or generic market-infrastructure terms that would
# otherwise fire on ordinary financial prose. Built empirically -- v1 of
# this resolver (case-insensitive symbol matching) produced real false
# positives on "oil"/"dollar"/"retail"/"worth"/"Shah" in the very first
# run against real data (see the B.5 report); this list + the case-
# sensitivity fix below are the direct fix, not a guess made in advance.
_STOPLIST = {
    "it", "on", "go", "up", "in", "at", "as", "is", "or", "to", "of", "gold",
    "idea", "info", "star", "route", "team", "wealth", "prime", "shine",
    "focus", "spark", "orbit", "pace", "trend", "vision", "value", "action",
    "asset", "credit", "capital", "finance", "future", "global", "growth",
    "india", "national", "united", "power", "energy", "steel", "bank",
    "industries", "international", "systems", "technologies", "solutions",
    # real false positives found in run v1 (case-insensitive symbol match):
    "oil", "dollar", "retail", "worth", "reliance", "shah",
    # exchange/platform names that are ALSO real listed companies, but in
    # RSS prose overwhelmingly refer to the generic exchange/platform, not
    # that company's own corporate news:
    "bse", "mcx", "nse",
    # real false positives found in run v2 (short/generic real company
    # core-names matching ordinary prose, or even a cricketer's first name
    # in "rishabh"'s case) -- a real company name being short is not the
    # same as it being SAFE to match on in free text:
    "take", "total", "race", "shree", "rishabh",
}
# Symbol matches require the LITERAL exact case as filed (e.g. "OIL", not
# "oil") -- real financial journalism prose essentially never writes a bare
# ticker in lowercase; a lowercase hit is what let "oil"/"dollar"/"retail"
# through in the first run. Name/alias matches stay case-insensitive since
# real company names are written consistently capitalized in prose either way.
_SYMBOL_CASE_SENSITIVE = True


def _strip_suffix(name: str) -> str:
    return _LEGAL_SUFFIXES.sub("", name).strip()


def _word_boundary_pattern(s: str, case_sensitive: bool) -> re.Pattern:
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])", flags)


async def _load_identifiers() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Two separate indices, matched differently on purpose (see the
    _SYMBOL_CASE_SENSITIVE comment above):
      name_index:   lowercased company_name/alias -> entity_ids, case-INsensitive match
      symbol_index: real-case symbol -> entity_ids, case-SENSITIVE match
    A string mapping to 2+ entity_ids in either index is inherently
    ambiguous and excluded entirely, never guessed at."""
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
    # Drop any identifier string that collides across multiple real
    # entities -- ambiguous, never resolved by guessing.
    name_index = {ident: next(iter(eids)) for ident, eids in name_raw.items() if len(eids) == 1}
    symbol_index = {ident: next(iter(eids)) for ident, eids in symbol_raw.items() if len(eids) == 1}
    ambiguous_count = (
        sum(1 for eids in name_raw.values() if len(eids) > 1)
        + sum(1 for eids in symbol_raw.values() if len(eids) > 1)
    )
    return name_index, symbol_index, ambiguous_count


async def resolve_text(text: str, title_len: int, name_index: dict[str, str], symbol_index: dict[str, str]) -> list[dict]:
    """Real whole-word matching. Names/aliases: case-insensitive (real
    company names are written consistently either way). Symbols: case-
    SENSITIVE (see _SYMBOL_CASE_SENSITIVE) -- this is the direct fix for
    the v1 false positives ("oil"/"dollar"/"retail" as lowercase prose
    words, not real ticker references)."""
    matches: dict[str, dict] = {}
    for ident, entity_id in name_index.items():
        if entity_id in matches:
            continue
        m = _word_boundary_pattern(ident, case_sensitive=False).search(text)
        if m:
            matches[entity_id] = {
                "entity_id": entity_id, "method": "name_or_alias",
                "matched_text": text[m.start():m.end()], "in_title": m.start() < title_len,
            }
    for ident, entity_id in symbol_index.items():
        if entity_id in matches:
            continue
        m = _word_boundary_pattern(ident, case_sensitive=_SYMBOL_CASE_SENSITIVE).search(text)
        if m:
            matches[entity_id] = {
                "entity_id": entity_id, "method": "symbol",
                "matched_text": text[m.start():m.end()], "in_title": m.start() < title_len,
            }
    return list(matches.values())


async def main() -> None:
    name_index, symbol_index, ambiguous_count = await build_index()
    print(f"real unambiguous name/alias identifiers: {len(name_index)}, symbol identifiers: {len(symbol_index)}")
    print(f"identifier strings dropped as ambiguous (collide across 2+ real entities): {ambiguous_count}\n")

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
        matches = await resolve_text(text, len(title), name_index, symbol_index)
        results.append({"id": r.id, "title": title, "summary": summary, "matches": matches})

    unlinked = [r for r in results if len(r["matches"]) == 0]
    single = [r for r in results if len(r["matches"]) == 1]
    multi = [r for r in results if len(r["matches"]) >= 2]

    print(f"total real RSS items: {len(results)}")
    print(f"  UNLINKED (0 matches): {len(unlinked)}")
    print(f"  SINGLE-entity: {len(single)}")
    print(f"  MULTI-entity (2+): {len(multi)}\n")

    print("=== sample SINGLE matches (first 30) ===")
    for r in single[:30]:
        m = r["matches"][0]
        print(f"  [{r['id'][:8]}] entity={m['entity_id']} method={m['method']} matched={m['matched_text']!r} in_title={m['in_title']}")
        print(f"     {r['title'][:110]!r}")

    print("\n=== sample MULTI matches (first 15) ===")
    for r in multi[:15]:
        ids = [(m["entity_id"], m["method"], m["matched_text"]) for m in r["matches"]]
        print(f"  [{r['id'][:8]}] {ids}")
        print(f"     {r['title'][:110]!r}")

    print("\n=== sample UNLINKED (first 15, sanity check -- should be genuinely no company) ===")
    for r in unlinked[:15]:
        print(f"  [{r['id'][:8]}] {r['title'][:110]!r}")

    import pickle
    with open("b5_resolver_results.pkl", "wb") as f:
        pickle.dump(results, f)
    print("\nfull results pickled to b5_resolver_results.pkl for the labeling pass")


if __name__ == "__main__":
    asyncio.run(main())

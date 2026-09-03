"""
B.5 Gate 1 resolver, v4 -- iteration 2 of 2 authorized by the owner on
2026-08-30 evening, after the v3 benchmark (77.3%/22.7% precision,
artifacts/b5_rss_entity_linkage_design_and_benchmark.md) found 5 real
false-positive classes. This version implements the 4 approved Gate-1
fixes (items 1-4 of that report's 6 next-iteration requirements); Gate 2
(item 5) is a separate script, b5_gate2_event_matching.py. Item 6
(re-benchmark) is the b5_benchmark_v4.py comparison this produces
results for.

Explicit owner mandate this pass: optimize precision, not coverage. A
fix that raises linkage counts by re-introducing any wrong-entity match
is a regression, not an improvement. "Recall can improve later" --
several real recall gaps found in v3 (single-word company names,
`Balrampur Chini`/`LIC`/`Indian Hotels` shortened-name misses) are
DELIBERATELY not chased here; see the "explicitly not fixed" section
below.

Four real, data-grounded fixes (grounded in actual DB rows queried
2026-08-30, not assumptions):

1. **Aggregator-suffix stripping.** Queried the real 630-item RSS
   corpus's title strings for trailing " - X" segments: 102/630 have
   one. The genuine publisher bylines (85 of the 102 -- "The Economic
   Times", "Moneycontrol.com", "NDTV Profit", "Groww", etc.) are ALL
   Title-Case / domain-style tokens with zero lowercase function words
   and never end in "?". The genuine headline continuations that also
   end in " - X" ("Which IPO Offers Better Listing Gains?", "Rally
   drive rationale explained", "How it will benefit shareholders")
   either end in "?" or contain lowercase non-connector words. The
   strip rule below is that real, observed boundary -- not a hardcoded
   list of known outlet names (a hardcoded list would miss any new
   Google-News-aggregated publisher; this rule is source-agnostic).

2. **CompanyAlias matching is now case-SENSITIVE, matched like symbols,
   not like names.** Queried real CompanyAlias rows: every single one
   is an uppercase code ("STANLEY", "20MICRONS", "360ONE",
   "3IINFOLTD") -- these are NSE/BSE scrip-style codes, not
   natural-language aliases a journalist would write in mixed case.
   The v3 false positive "'Stanley' inside 'Morgan Stanley'" was a
   direct consequence of matching this code case-insensitively. Since
   0/630 real titles are ALL-CAPS (queried), case-sensitive alias
   matching costs no real recall and closes this FP class at the root
   -- not via a hand-added guard for this one instance.

3. **Single-word `company_name` matches are excluded; canonical-name
   matching now requires 2+ words.** Every one of v3's "generic
   English word" false positives (persistent, deep, rain, spectrum,
   clean, advance, suraksha, affordable, gopal, take, total, race,
   shree, rishabh, oil, dollar, retail, worth, shah) was a SINGLE-WORD
   company_name or alias match. Real data showed case-sensitivity
   alone does not fully close this class -- Indian RSS headlines are
   frequently Title-Cased ("Toxic Advance Booking Day 1..."), which
   re-capitalizes ordinary words for formatting reasons unrelated to
   any company reference ("Advance", "Rain" both recurred capitalized
   in real Title-Case headlines having nothing to do with those
   companies). A systematic length-based rule -- not a frequency
   dictionary, not another hand list -- removes the entire class:
   single-word canonical names are structurally unsafe to match in
   free text; a company only reachable by a single-word name is still
   reachable via its SYMBOL (case-sensitive, unaffected by this
   change). This trades away a real, acknowledged recall segment
   (single-word-named companies mentioned by name without their
   ticker) for the precision the owner asked for.

4. **Proper-noun collision guard, kept small and explicit.** "Bank of
   India" (a real, distinct 3-word company_name, confirmed via query
   against 3 other real "X Bank of India" entities) is not itself
   ambiguous -- no other CompanyEntity string collides with it -- so
   the existing ambiguous-collision-drop logic cannot catch its real
   collision with "Reserve Bank of India" (the regulator, not itself a
   listed company/entity row). This is architecturally a different
   problem from ambiguity: a well-known, non-listed institution whose
   name happens to CONTAIN a real listed company's exact name. A small,
   explicit, extensible guard table records known cases like this one
   -- unlike the single-word stoplist (proven not to converge across 3
   iterations of ordinary-English-word collisions), this class is
   narrow (well-known institution names are a small, roughly fixed
   set) and is expected to need only occasional, evidence-driven
   additions, not the same open-ended growth.

Explicitly NOT fixed this pass (real, acknowledged, deliberately
deferred per the precision-first mandate -- "don't tune thresholds to
make recall look better"):
  - Iterative/headline-aware legal-suffix stripping to recover
    `Balrampur Chini`/`Indian Hotels`-style shortened multi-entity
    misses: the *iterative* stripping of compound legal suffixes
    (e.g. "X Company Limited" -> strip "Limited" -> "X Company" ->
    strip "Company" -> "X") IS included below, since a single-pass
    regex missing a compound suffix is a real bug, not a recall
    trade-off. But generating additional SHORTENED name variants
    beyond legal-suffix stripping (e.g. guessing "Indian Hotels" from
    "Indian Hotels Company Limited" by also dropping "Company") is NOT
    done -- that is exactly the kind of recall-chasing heuristic that
    risks new false positives, and the owner's instruction was
    explicit that recall stays deferred.
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

# ── Fix 1: aggregator-suffix stripping ──────────────────────────────────
# A trailing " - <segment>" is treated as a publisher byline (stripped
# before entity resolution, title only) iff every word in <segment> is
# either capitalized/ALL-CAPS, a short lowercase connector ("of", "on",
# "and", "&", "the"), or a domain-style token (foo.com/.in/.co), AND the
# segment does not end in "?", AND the segment is <=6 words. This is the
# real, observed shape of the 85 genuine bylines found in the 630-item
# corpus (see module docstring) -- not a name lookup against any known
# outlet list, so it generalizes to publishers not yet seen.
_CONNECTOR_WORDS = {"of", "on", "and", "&", "the", "in", "for"}
_TRAILING_SEGMENT = re.compile(r"^(?P<headline>.+?)\s+-\s+(?P<suffix>[^-]{2,60})$")


def _looks_like_byline(segment: str) -> bool:
    segment = segment.strip()
    if not segment or segment.endswith("?"):
        return False
    words = segment.split()
    if len(words) > 6:
        return False
    for w in words:
        bare = w.strip(".,")
        if not bare:
            continue
        if bare.lower() in _CONNECTOR_WORDS:
            continue
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9&']*\.(com|in|co)$", bare, re.IGNORECASE):
            continue  # domain-style token, e.g. "livemint.com"
        if bare[0].isupper() or bare.isupper() or bare.isdigit():
            continue
        return False  # a genuine lowercase content word -> not a byline
    return True


def strip_aggregator_suffix(title: str) -> str:
    m = _TRAILING_SEGMENT.match(title or "")
    if m and _looks_like_byline(m.group("suffix")):
        return m.group("headline").strip()
    return title or ""


# ── Fix 1, completion found during v4 census review ──────────────────────
# Google News RSS summaries wrap the byline in its own tag, separate from
# the headline: '<a href="...">{headline}</a>&nbsp;&nbsp;<font
# color="#6f6f6f">{Publisher}</font>' -- confirmed by pulling one real,
# untruncated summary (the "NDTV" false positives: 5 of the 10 wrong
# matches found in the first v4 census run were this exact shape, e.g.
# "...Ram Navami Today? Check NSE, BSE Holiday List</a>...<font...>NDTV
# </font>"). The trailing-dash heuristic above was built for the TITLE
# field's convention and never looks at the summary; stripping this font
# span is the completion of the same real fix (source-artifact
# contamination), not a new mechanism.
_GOOGLE_NEWS_BYLINE_FONT = re.compile(r"<font[^>]*>.*?</font>", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_ENTITY = re.compile(r"&(nbsp|amp|#39|quot|zwj|zwnj);?")


def clean_summary_for_matching(summary: str) -> str:
    s = _GOOGLE_NEWS_BYLINE_FONT.sub(" ", summary or "")
    s = _HTML_TAG.sub(" ", s)
    s = _HTML_ENTITY.sub(" ", s)
    return s


# Also found in the same census: a Reuters-style wire dateline tag
# ("GLOBAL-FOREX/ (UPDATE 5):FOREX-Dollar falls...") collided with a real
# case-sensitive alias literally spelled "GLOBAL". Not a byline (no dash-
# separated trailing segment, no font tag) -- a different real source-
# artifact shape: an ALL-CAPS wire-service section tag immediately
# followed by a hyphen and another all-caps word and a slash. Guarding
# this exact shape is the same "don't trust source-formatting artifacts"
# principle as fix 1, applied to the one additional real shape found.
_WIRE_DATELINE_TAG = re.compile(r"-[A-Z]{2,}/")


def _is_wire_dateline_artifact(text: str, start: int, end: int) -> bool:
    return bool(_WIRE_DATELINE_TAG.match(text, end))


# ── Fix 3/4 support: legal-suffix stripping (now iterative) ─────────────
_LEGAL_SUFFIX_TOKEN = re.compile(
    r"\s+(limited|ltd\.?|private limited|pvt\.? ltd\.?|corporation|corp\.?|inc\.?|plc|llp|company|"
    r"& co\.?|and company|co\.? ltd\.?)\s*$",
    re.IGNORECASE,
)
_TRAILING_PAREN = re.compile(r"\s*\((india|the)\)\s*$", re.IGNORECASE)


def strip_legal_suffix_iterative(name: str) -> str:
    """Single-pass suffix stripping missed compound forms like
    'X Company Limited' (real bug, not a recall trade-off) -- loop until
    a pass makes no further change.

    Guard found via the v3-vs-v4 diff after this fix first shipped:
    'corp'/'corporation' is in the legal-suffix list because 'X
    Corporation Limited' -> 'X Corporation' -> 'X' is a real compound
    case. But for a company whose stable, real short-form IS "X Corp"
    (e.g. "Welspun Corp" -- real financial prose never shortens this
    further to bare "Welspun"), stripping "Corp" as if it were as
    disposable as "Limited" reduced a real, safe 2-word identifier to a
    single word, which fix 3 then correctly-but-unintentionally
    dropped as unsafe. Since "Limited"/"Ltd"/"Pvt Ltd"/etc. are never
    themselves part of how a company is actually referred to in prose,
    but "Corp"/"Corporation" sometimes is, only strip corp/corporation
    when at least one other legal-suffix token also matched in the same
    pass (i.e. it was trailing something ALSO disposable, like
    "X Corporation Limited") -- never as the sole, final strip that
    would leave one word."""
    # "Corp"/"Corporation"/"Company" are ambiguous suffix tokens -- for
    # most companies they're a disposable corporate-form descriptor
    # ("XYZ Corporation Limited" -> "XYZ"), but for some, the token is
    # part of the real, stable short-form name itself that prose never
    # drops further ("Welspun Corp", "Urban Company Limited" -> "Urban
    # Company" -- both real, confirmed via the v3-vs-v4 diff: both were
    # correctly matching real headlines under v3's single-pass stripping
    # and were wrongly lost once this fix made stripping iterative).
    # "Limited"/"Ltd"/"Private Limited"/"Inc"/"plc"/"llp" carry no such
    # ambiguity -- prose never keeps them -- so only these three tokens
    # get the do-not-reduce-below-2-words floor.
    _ambiguous_suffix = re.compile(r"\s+(corporation|corp\.?|company)\s*$", re.IGNORECASE)
    prev = None
    current = name
    while current != prev:
        prev = current
        after_main = _LEGAL_SUFFIX_TOKEN.sub("", current).strip()
        if len(after_main.split()) < 2 and len(current.split()) >= 2 and _ambiguous_suffix.search(current):
            break
        current = after_main
        current = _TRAILING_PAREN.sub("", current).strip()
    return current


# ── Fix 4: proper-noun collision guards ──────────────────────────────────
# identifier (lowercased) -> set of poison prefix words (lowercased) that,
# found immediately before the match, mean it's actually part of a
# DIFFERENT real institution's name, not this company. Kept small and
# explicit on purpose -- see module docstring for why this class doesn't
# need (and shouldn't get) open-ended growth like the old stoplist.
_SUPERSTRING_GUARDS: dict[str, set[str]] = {
    "bank of india": {"reserve"},   # "Reserve Bank of India" is the regulator, not this company
}

_STOPLIST = {
    # retained as a defensive backstop for SYMBOLS only now that names are
    # multi-word-only and aliases are case-sensitive (see module docstring,
    # fixes 2/3) -- most of these entries are now redundant with those
    # structural fixes but cost nothing to keep.
    "it", "on", "go", "up", "in", "at", "as", "is", "or", "to", "of",
    "bse", "mcx", "nse",
}
_SYMBOL_CASE_SENSITIVE = True


def _build_combined_pattern(idents: list[str], case_sensitive: bool) -> re.Pattern | None:
    """One compiled alternation per bucket instead of one compile per
    identifier per row -- the original per-identifier-per-call approach
    was ~7,500 identifiers x 630 rows = millions of re.compile() calls,
    which is what actually made the real run hang for minutes (not a DB
    lock, as first suspected). Longest-first ordering so overlapping
    identifiers (rare, but real given the ambiguous-collision drop
    already removes exact duplicates) still prefer the longest match."""
    if not idents:
        return None
    flags = 0 if case_sensitive else re.IGNORECASE
    ordered = sorted(idents, key=len, reverse=True)
    body = "|".join(re.escape(i) for i in ordered)
    return re.compile(r"(?<![A-Za-z0-9])(" + body + r")(?![A-Za-z0-9])", flags)


async def _load_identifiers():
    """Three separate indices now (was two in v3), matched differently
    because real data showed they are three genuinely different kinds of
    string (see module docstring, fix 2):
      name_index:   lowercased, MULTI-WORD-ONLY company_name -> entity_id, case-INsensitive
      alias_index:  real-case CompanyAlias.alias_value -> entity_id, case-SENSITIVE (code-like)
      symbol_index: real-case CompanyEntity.symbol -> entity_id, case-SENSITIVE (unchanged from v3)
    A string colliding across 2+ entities within its own bucket is
    dropped entirely, never guessed."""
    async with AsyncSessionLocal() as db:
        entities = (await db.execute(select(CompanyEntity.entity_id, CompanyEntity.company_name, CompanyEntity.symbol))).all()
        aliases = (await db.execute(select(CompanyAlias.entity_id, CompanyAlias.alias_value))).all()

    name_raw: dict[str, set[str]] = defaultdict(set)
    alias_raw: dict[str, set[str]] = defaultdict(set)
    symbol_raw: dict[str, set[str]] = defaultdict(set)
    single_word_names_dropped = 0

    for entity_id, company_name, symbol in entities:
        # Matched case-SENSITIVE against the literal stored casing (found
        # during v4 census review: case-insensitive matching let "Indian
        # bank stocks..." collide with the real company "Indian Bank",
        # which IS stored in correct Title Case -- confirmed by querying
        # the real row). A blanket .title()-normalization was considered
        # and rejected: it would have LOWERCASED real, correctly-stored
        # acronym names like "HDFC Bank" to "Hdfc Bank" (Python's
        # str.title() only capitalizes each word's first letter), breaking
        # every real HDFC/ICICI/IDBI-style match. Matching the literal
        # stored casing costs recall only on the rare company_name rows
        # confirmed earlier to be stored in all-lower/all-upper form
        # ("63 moons technologies limited", "360 ONE WAM LIMITED") --
        # an acceptable, narrow trade per the precision-first mandate.
        core = strip_legal_suffix_iterative(company_name or "")
        if len(core) >= 4 and core.lower() not in _STOPLIST:
            if len(core.split()) >= 2:
                name_raw[core].add(entity_id)
            else:
                single_word_names_dropped += 1
        sym = symbol or ""
        if len(sym) >= 3 and sym.lower() not in _STOPLIST:
            symbol_raw[sym].add(entity_id)

    for entity_id, alias_value in aliases:
        a = (alias_value or "").strip()
        if len(a) >= 3 and a.lower() not in _STOPLIST:
            alias_raw[a].add(entity_id)

    return name_raw, alias_raw, symbol_raw, single_word_names_dropped


async def build_index():
    name_raw, alias_raw, symbol_raw, single_word_dropped = await _load_identifiers()
    name_index = {ident: next(iter(eids)) for ident, eids in name_raw.items() if len(eids) == 1}
    alias_index = {ident: next(iter(eids)) for ident, eids in alias_raw.items() if len(eids) == 1}
    symbol_index = {ident: next(iter(eids)) for ident, eids in symbol_raw.items() if len(eids) == 1}
    ambiguous_count = (
        sum(1 for eids in name_raw.values() if len(eids) > 1)
        + sum(1 for eids in alias_raw.values() if len(eids) > 1)
        + sum(1 for eids in symbol_raw.values() if len(eids) > 1)
    )
    return name_index, alias_index, symbol_index, ambiguous_count, single_word_dropped


def _guard_blocks(text: str, ident: str, start: int) -> bool:
    poison = _SUPERSTRING_GUARDS.get(ident.lower())
    if not poison:
        return False
    prefix = text[:start].rstrip()
    prev_word_match = re.search(r"([A-Za-z]+)\s*$", prefix)
    if not prev_word_match:
        return False
    return prev_word_match.group(1).lower() in poison


def _scan_bucket(text: str, title_len: int, pattern: re.Pattern | None, index: dict[str, str],
                  method: str, case_sensitive: bool, matches: dict[str, dict]) -> None:
    if pattern is None:
        return
    for m in pattern.finditer(text):
        matched_text = m.group(1)
        key = matched_text if case_sensitive else matched_text.lower()
        entity_id = index.get(key)
        if entity_id is None or entity_id in matches:
            continue
        if method == "name" and _guard_blocks(text, key, m.start()):
            continue
        if method in ("alias", "symbol") and _is_wire_dateline_artifact(text, m.start(), m.end()):
            continue
        matches[entity_id] = {
            "entity_id": entity_id, "method": method,
            "matched_text": matched_text, "in_title": m.start() < title_len,
        }


async def resolve_text(text: str, title_len: int, patterns: dict, name_index, alias_index, symbol_index) -> list[dict]:
    matches: dict[str, dict] = {}
    _scan_bucket(text, title_len, patterns["name"], name_index, "name", True, matches)
    _scan_bucket(text, title_len, patterns["alias"], alias_index, "alias", True, matches)
    _scan_bucket(text, title_len, patterns["symbol"], symbol_index, "symbol", _SYMBOL_CASE_SENSITIVE, matches)
    return list(matches.values())


async def main() -> None:
    name_index, alias_index, symbol_index, ambiguous_count, single_word_dropped = await build_index()
    print(f"v4 real unambiguous identifiers: names(multi-word)={len(name_index)} aliases={len(alias_index)} symbols={len(symbol_index)}")
    print(f"single-word company_name entries dropped by design (fix 3): {single_word_dropped}")
    print(f"identifier strings dropped as ambiguous (collide across 2+ real entities): {ambiguous_count}\n")

    patterns = {
        "name": _build_combined_pattern(list(name_index.keys()), case_sensitive=True),
        "alias": _build_combined_pattern(list(alias_index.keys()), case_sensitive=True),
        "symbol": _build_combined_pattern(list(symbol_index.keys()), case_sensitive=_SYMBOL_CASE_SENSITIVE),
    }

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
        raw_title = r.title or ""
        title = strip_aggregator_suffix(raw_title)
        raw_summary = payload.get("summary", "")
        summary = clean_summary_for_matching(raw_summary)
        text = f"{title} {summary}"
        matches = await resolve_text(text, len(title), patterns, name_index, alias_index, symbol_index)
        results.append({"id": r.id, "title": raw_title, "title_stripped": title, "summary": raw_summary, "matches": matches})

    unlinked = [r for r in results if len(r["matches"]) == 0]
    single = [r for r in results if len(r["matches"]) == 1]
    multi = [r for r in results if len(r["matches"]) >= 2]

    print(f"total real RSS items: {len(results)}")
    print(f"  UNLINKED (0 matches): {len(unlinked)}")
    print(f"  SINGLE-entity: {len(single)}")
    print(f"  MULTI-entity (2+): {len(multi)}\n")

    stripped_count = sum(1 for r in results if r["title"] != r["title_stripped"])
    print(f"titles with aggregator suffix stripped: {stripped_count}\n")

    import pickle
    with open("b5_resolver_results_v4.pkl", "wb") as f:
        pickle.dump(results, f)
    print("full v4 results pickled to b5_resolver_results_v4.pkl")


if __name__ == "__main__":
    asyncio.run(main())

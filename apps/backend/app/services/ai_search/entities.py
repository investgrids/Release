"""
Entity extraction for the AI Search V3 pipeline — extends V2's exact/alias
company matching (`_match_companies` in ai_search_service.py, reused
unchanged here) with fuzzy matching for misspellings, and returns canonical,
resolved entities rather than raw matched text, so downstream specialists and
the deterministic validator (validation.py) can trust `companies[]` actually
exist in the real NSE universe.

No new third-party dependency — uses stdlib `difflib`, since a fuzzy-matching
library (rapidfuzz/python-Levenshtein) isn't currently vendored and adding
one is a decision better made once real precision/recall numbers exist (see
plan's Open Risks). Universe-expansion investigation (2026-08-09) measured
this scaling badly with corpus size when each comparison built a fresh
SequenceMatcher from nothing (~1s at 510 companies -> ~3.7s at a ~2,300
proxy scale) — fixed by caching the corpus and reusing SequenceMatcher's
per-token b2j index across a whole comparison pass (see `_corpus`/
`_fuzzy_candidates`), the same reuse pattern stdlib's own
`difflib.get_close_matches` already uses internally. Still O(query n-grams x
corpus size) in comparison count, just with the expensive per-comparison
setup work removed — worth re-measuring if the universe grows enough that
raw comparison count itself becomes the bottleneck again.
"""
from __future__ import annotations

import difflib
import re

from app.services.ai_search.regexes import _POLICIES, _SECTORS

# Word-boundary anchoring for short sector/policy tokens that are also
# substrings of unrelated common words — "it" (IT sector) inside "its",
# "pli" (Production Linked Incentive) inside "compliance". Ported from
# V2's identical fix (ai_search_service.py's _SHORT_TOKEN_RE/_term_in_query).
# Deliberately scoped to only these two: everything else in _SECTORS/
# _POLICIES is either a multi-word phrase or long/distinctive enough that
# no real collision has been found — blanket \b-anchoring risks breaking
# legitimate substring matches this codebase has no evidence about either
# way (e.g. "auto" inside "automobile").
_SHORT_TOKEN_RE = {
    "it": re.compile(r"\bit\b"),
    "pli": re.compile(r"\bpli\b"),
}


def _term_in_query(term: str, q: str) -> bool:
    pat = _SHORT_TOKEN_RE.get(term)
    return bool(pat.search(q)) if pat else term in q


# Strong signal: a capitalized phrase ending in a real corporate suffix —
# e.g. "Bharat Quantum Computing Ltd". High-confidence enough that a
# coincidental sector word elsewhere in the same phrase ("XYZ Defence Ltd")
# shouldn't override it — "Ltd"/"Corp"/etc. essentially never appears in a
# genuine sector/macro/policy question.
_COMPANY_SUFFIX_RE = re.compile(
    r"\b(?:[A-Z][a-zA-Z]*\s+){1,5}"
    r"(?:Ltd\.?|Limited|Inc\.?|Corp\.?|Corporation|Industries|Technologies|"
    r"Systems|Holdings|International|Enterprises|Group|Motors|Pharma|Energy)\b"
)
# Weak signal: a bare 2+ capitalized-word phrase with no corporate suffix —
# e.g. "Tata Neuralink". Realistic company names can be this short, so the
# minimum is 2 words, not 3 — but with no suffix to lean on, this tier stays
# gated on zero sector/policy signal too (see caller), unlike the strong tier.
_COMPANY_BARE_RE = re.compile(r"\b(?:[A-Z][a-zA-Z]{2,}\s+){1,4}[A-Z][a-zA-Z]{2,}\b")

# P3: narrow signal for a SINGLE capitalized word immediately followed by a
# stock-specific noun — "What's the outlook for Apple stock?" ("Apple"
# alone doesn't satisfy _COMPANY_BARE_RE's 2-word minimum, and has no
# corporate suffix, so it fell through both existing detectors undetected
# — verified live). Deliberately narrow: catching every single capitalized
# word here would false-positive on legitimate phrasing like "Indian stock
# market" or "Global shares outlook" — _GENERIC_STOCK_PREFIX excludes the
# common non-company descriptors this pattern would otherwise misfire on.
_GENERIC_STOCK_PREFIX = {
    "indian", "india", "us", "global", "foreign", "international", "domestic",
    "local", "asian", "american", "chinese", "european", "any", "some",
    "penny", "blue", "small", "large", "mid", "growth", "value", "dividend",
}
_SINGLE_WORD_STOCK_RE = re.compile(
    r"\b([A-Z][a-zA-Z]{2,})\s+(?:stock|shares|share\s+price|stock\s+price)\b"
)


def _match_companies(q: str) -> list[str]:
    """
    Word-boundary-aware alias matching. Plain substring containment (the
    original implementation) let short tickers/aliases match inside
    unrelated words — found live via a broad test sweep: "ITC" matched
    inside "sw-ITC-h", "REC" matched inside "REC-ent", "LIC" matched inside
    "po-LIC-y". Every one of those produced a spurious extra company in the
    response with no real connection to the query.

    Step 3C, Case B — span-based cross-company suppression. Word-boundary
    matching alone still let a shorter alias belonging to one company match
    INSIDE a longer alias already claimed by a different company: "Tech
    Mahindra" (TECHM's own alias) also contains M&M's alias "mahindra" as a
    valid word-boundary substring, so both used to resolve independently —
    found live, confirmed a real ~200-company alias-table collision, not a
    one-off. Fix: find every company's best (longest) matching span first,
    then keep spans longest-first, dropping any shorter span that's fully
    CONTAINED within an already-claimed span. A shorter alias on a
    genuinely separate, non-overlapping occurrence of the same word still
    resolves independently (e.g. "Mahindra Group and Tech Mahindra" keeps
    both M&M and TECHM) — only same-text containment is suppressed.
    """
    from app.api.companies import _NSE_UNIVERSE
    # (span_start, span_end, symbol) — one best span per company.
    candidates: list[tuple[int, int, str]] = []
    for co in _NSE_UNIVERSE:
        aliases = (co.get("aliases") or []) + [co["name"].lower(), co["symbol"].lower()]
        best: tuple[int, int] | None = None
        for a in aliases:
            if len(a) < 3:
                continue
            start = 0
            while True:
                idx = q.find(a, start)
                if idx == -1:
                    break
                before_ok = idx == 0 or not q[idx - 1].isalnum()
                end = idx + len(a)
                after_ok = end == len(q) or not q[end].isalnum()
                if before_ok and after_ok and (best is None or (end - idx) > (best[1] - best[0])):
                    best = (idx, end)
                start = idx + 1
        if best is not None:
            candidates.append((best[0], best[1], co["symbol"]))

    # Suppression decided on a longest-span-first pass, but the RETURNED
    # order still follows _NSE_UNIVERSE order (unchanged from before this
    # fix) -- callers downstream (e.g. the 3-way compare's matches[:3] cap)
    # rely on that ordering; only which symbols survive should change here,
    # not the order they come back in.
    claimed: list[tuple[int, int]] = []
    suppressed: set[str] = set()
    for start, end, sym in sorted(candidates, key=lambda c: c[1] - c[0], reverse=True):
        if any(start >= cs and end <= ce for cs, ce in claimed):
            suppressed.add(sym)
            continue
        claimed.append((start, end))

    matched: list[str] = []
    seen: set[str] = set()
    for _start, _end, sym in candidates:
        if sym in suppressed or sym in seen:
            continue
        matched.append(sym)
        seen.add(sym)
    return matched


def _looks_like_unrecognized_company(query: str, entities: dict) -> bool:
    """High-confidence-only signal that the query names a specific company
    not in our real ~202-company NSE universe — used to short-circuit
    straight to an honest "no verified company found" response instead of
    letting the LLM either analyze a fictional entity or fall through to
    the generic degraded-synthesis template (which reads as "we have real
    data but couldn't finish the analysis", not "this company doesn't
    exist" — the wrong message for a fabricated name).

    Handles mixed queries too — e.g. "Compare Apple India Defence Ltd vs
    HAL" has one real match (HAL) and one fake one; a naive "any real match
    disqualifies this" rule would let the fake half through silently. Real
    company text is stripped out first, then the residual is checked for a
    still-unaccounted-for company-shaped phrase.
    """
    residual = query
    if entities["companies"]:
        from app.api.companies import _NSE_UNIVERSE
        matched_set = set(entities["companies"])
        for co in _NSE_UNIVERSE:
            if co["symbol"] not in matched_set:
                continue
            # Step 3C, Case E — longest-first, same strategy extract_entities()
            # already uses for the identical reason (see its own comment):
            # stripping a short alias before a longer one fragments it,
            # leaving a bare remainder ("ceutical" from "Sun Pharmaceutical"
            # once "sun pharma" strips first). Each alias pattern also
            # optionally consumes one generic corporate-suffix word
            # (Ltd/Industries/Corp/...) DIRECTLY ADJACENT to that specific
            # occurrence — confirmed live: RELIANCE's alias list is only
            # ["reliance", "ril"], never "Reliance Industries", so plain
            # alias stripping left a bare "Industries" behind that then
            # matched _COMPANY_SUFFIX_RE and false-flagged an already-
            # resolved company as unrecognized. Deliberately positional, not
            # a blanket strip of every occurrence of that suffix word
            # anywhere in the query — an EARLIER version of this fix that
            # added the company's own name-words as global strip candidates
            # regressed the documented "Compare Apple India Defence Ltd vs
            # HAL" mixed case: HAL's own name also ends in "Ltd", so a
            # global strip erased "Ltd" from the UNRELATED fake company's
            # text too, hiding its suffix signal. Adjacency keeps each
            # consumption scoped to the actual matched occurrence.
            _SUFFIX_ALT = "|".join(re.escape(w) for w in _GENERIC_SUFFIX_WORDS)
            strip_candidates = sorted(
                {a for a in (co.get("aliases") or []) + [co["name"], co["symbol"]] if len(a) >= 3},
                key=len, reverse=True,
            )
            for alias in strip_candidates:
                pattern = re.escape(alias) + rf"(\s+(?:{_SUFFIX_ALT})\b)?"
                residual = re.sub(pattern, " ", residual, flags=re.IGNORECASE)
        # Mixed case: only the high-confidence suffix signal counts on the
        # residual — leftover connector words ("Compare", "vs") after
        # stripping real names could spuriously look bare-capitalized.
        return bool(_COMPANY_SUFFIX_RE.search(residual))

    if _COMPANY_SUFFIX_RE.search(residual):
        return True
    if entities["sectors"] or entities["policies"]:
        return False
    if _COMPANY_BARE_RE.search(residual):
        return True
    # P3: single-word unsupported-entity case ("Apple stock") — see
    # _SINGLE_WORD_STOCK_RE's comment for why this is deliberately narrow.
    m = _SINGLE_WORD_STOCK_RE.search(residual)
    return bool(m and m.group(1).lower() not in _GENERIC_STOCK_PREFIX)

# Below this ratio, a fuzzy candidate is too weak to trust as a real match —
# only used as a "did you mean" suggestion, never silently substituted in.
_FUZZY_MATCH_CUTOFF = 0.82
# Looser cutoff purely for surfacing suggestions when nothing matched at all.
_FUZZY_SUGGEST_CUTOFF = 0.6


def _universe() -> list[dict]:
    from app.api.companies import _NSE_UNIVERSE
    return _NSE_UNIVERSE


# Module-level cache, keyed by id(_NSE_UNIVERSE) — invalidated only when the
# universe list itself changes (which in practice only happens across a
# process restart on a code deploy; nothing mutates it in place at runtime,
# confirmed by grep across every consumer). Universe-expansion investigation
# (2026-08-09) measured entity extraction going from ~1s to ~3.7s per query
# as the corpus grew, root-caused to two compounding costs paid on every
# single call: this list rebuilt from scratch, and (in _fuzzy_candidates
# below) a fresh difflib.SequenceMatcher constructed per (token, corpus-
# entry) pair with no reuse of either side's precomputed index.
_CORPUS_CACHE: dict[int, list[tuple[str, str, dict]]] = {}

# Same id()-keyed caching pattern as _CORPUS_CACHE, same reason — Case C's
# owner-count check (both the corpus-side filter in _corpus() and the
# query-side filter in _fuzzy_candidates()) would otherwise re-scan the
# whole universe on every single call, and _fuzzy_candidates is called once
# per n-gram per query.
_NAME_WORD_OWNERS_CACHE: dict[int, dict[str, int]] = {}


# Step 3C, Case C — a single-word core shared by this many or more DISTINCT
# companies carries no real per-company identifying signal on its own (see
# _corpus()'s own comment for the confirmed live case). Deterministic and
# self-maintaining: computed from the real universe every time, not a
# hand-curated word list that goes stale as the universe grows.
_NON_DISTINCTIVE_MIN_OWNERS = 3


def _name_word_owner_counts() -> dict[str, int]:
    """How many DISTINCT companies have each word anywhere in their full
    name — not just as some other company's own collapsed single-word
    core (that undercounts badly: "india" is the collapsed core for only
    3M India itself, since most other companies naming India retain other
    distinguishing words too — but "india" still appears as a plain word
    in 75 different companies' names, which is the real signal that it's
    a common qualifier, not a per-company identifier)."""
    universe = _universe()
    key = id(universe)
    cached = _NAME_WORD_OWNERS_CACHE.get(key)
    if cached is not None:
        return cached
    _NAME_WORD_OWNERS_CACHE.clear()
    counts: dict[str, set[str]] = {}
    for co in universe:
        for w in {w.lower() for w in _WORD_RE.findall(co["name"]) if len(w) >= 3}:
            counts.setdefault(w, set()).add(co["symbol"])
    result = {w: len(syms) for w, syms in counts.items()}
    _NAME_WORD_OWNERS_CACHE[key] = result
    return result


def _corpus() -> list[tuple[str, str, dict]]:
    """(searchable_text, stripped_core_text, company_row) triples — name,
    symbol, and every alias, each pointing back to its parent row so a fuzzy
    hit resolves to the real canonical symbol regardless of which alias it
    matched against. The stripped-core form is precomputed once here rather
    than recomputed on every fuzzy comparison (it used to be recomputed once
    per (token, entry) pair — the same text stripped identically every time).

    Step 3C, Case C — excludes non-distinctive single-word cores. Confirmed
    live: "3M India Ltd"'s own core collapses to the bare word "india" --
    _WORD_RE requires a letter to start a token, so the digit-led "3M" is
    silently dropped entirely, and "Ltd" is stripped as a generic suffix --
    leaving a core indistinguishable from the literal word "india", which
    then matches ratio 1.0 against ANY query naming India as a plain
    country qualifier (e.g. "Colgate-Palmolive India"). Fixed by rejecting
    any single-word core (no space) that also appears as a plain word in
    3+ OTHER distinct companies' full names anywhere in the universe --
    "india" clears that bar by a wide margin (75 companies); a real
    per-company identifier ("infosys", "reliance") never does."""
    universe = _universe()
    key = id(universe)
    cached = _CORPUS_CACHE.get(key)
    if cached is not None:
        return cached
    _CORPUS_CACHE.clear()

    owner_counts = _name_word_owner_counts()
    pairs: list[tuple[str, str, dict]] = []
    for co in universe:
        texts = {co["name"].lower(), co["symbol"].lower(), *[a.lower() for a in (co.get("aliases") or [])]}
        for t in texts:
            core = _strip_generic(t)
            if len(core) < 3:
                continue
            if " " not in core and owner_counts.get(core, 0) >= _NON_DISTINCTIVE_MIN_OWNERS:
                continue
            pairs.append((t, core, co))
    _CORPUS_CACHE[key] = pairs
    return pairs


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z&.]{1,}")

# Generic corporate-suffix / connector words that are too common to trust as
# a *standalone* fuzzy match key — e.g. the bare word "Industries" fuzzy-
# matches "PI Industries Ltd" at a deceptively high ratio (it's a genuine
# substring) despite carrying no company-identifying signal on its own.
# Multi-word n-grams that merely *contain* one of these are fine and still
# checked — only a 1-word n-gram consisting of just this word is skipped.
_GENERIC_SUFFIX_WORDS = {
    "ltd", "limited", "inc", "corp", "corporation", "industries", "technologies",
    "systems", "holdings", "international", "enterprises", "group", "motors",
    "pharma", "energy", "bank", "finance", "financial", "services", "company",
    "consultancy", "solutions", "products", "power", "steel", "cement",
}

# P5 Stage 4 — ordinary English words confirmed live to fuzzy-match a real
# company's SHORT alias at a deceptively high ratio, despite carrying no
# company-identifying signal: "latest" -> "latent" (Latent View Analytics,
# 0.83), "continue" -> "container" (Container Corp, 0.82), "infrastructure"
# -> "gmr/irb/jsw infrastructure" (0.875 — a large fraction of each short
# alias's own length, the same substring-inflation failure _GENERIC_SUFFIX_
# WORDS already exists to prevent, just not yet covering this word).
# _GENERIC_SUFFIX_WORDS doesn't fit these — they're not corporate-suffix
# words, they're ordinary vocabulary that happens to collide. Different
# mechanism from a misspelling: a real English word used correctly isn't a
# typo of anything, so excluding it costs nothing on the legitimate-match
# side (verified: none of "Relaince"/"Infosis"/"HDFC Bnak"/"Infy" are real
# dictionary words, and none are in this list). Quantified via a ~105-word
# scan of ordinary query vocabulary: only these 3 triggered — a real but
# bounded pattern (~3%), not systemic. Same curation model as
# _GENERIC_SUFFIX_WORDS above: seeded from confirmed cases, grown as new
# ones are found live, not a preemptive dictionary.
_FUZZY_EXCLUDED_WORDS = {
    "latest", "continue", "infrastructure",
}

# Step 3D — query-framing vocabulary. Confirmed live: "What is the
# INVESTMENT outlook for Asian Paints?" fuzzy-matched the 1-gram
# "investment" (and the 2-gram "investment outlook") against TATAINVEST's
# own stripped core "tata investment" (from "Tata Investment Corporation
# Ltd") at ratio 0.83 -- injecting a completely unrelated financial holding
# company into a paints-company query, which the LLM then rationalized
# with plausible-sounding but fabricated reasoning. Same underlying failure
# class as _GENERIC_SUFFIX_WORDS/_FUZZY_EXCLUDED_WORDS (an ordinary word
# that happens to be a substantial fraction of some real company's short
# core), but these are QUERY-FRAMING words -- "how the user asked the
# question" -- not company-name or corporate-suffix vocabulary, so they get
# their own small, explicitly-justified set rather than being folded into
# either existing one. Reuses _word_ngrams' existing "all words in this
# n-gram are generic -> skip the whole gram" mechanism (see below), which
# already gives exactly the right behavior for the acceptance cases: a gram
# that ALSO contains a real distinctive word ("Tata Investment Corporation"
# -- "tata" isn't generic) still survives and can fuzzy-match normally.
# Seeded from this one confirmed case plus its immediate query-phrasing
# variants, not a preemptive dictionary — same curation model as
# _FUZZY_EXCLUDED_WORDS above.
_QUERY_FRAMING_WORDS = {
    "investment", "investments", "invest", "should", "outlook",
    "stock", "stocks", "share", "shares",
}

# Plain English function words — "the", "is", "for", etc. Only relevant to
# the gate check below, never to _strip_generic's core computation: a
# company's own name never legitimately contains one of these as its
# distinguishing word, but a QUERY frequently does ("What is THE INVESTMENT
# outlook..."), and without recognizing them as non-distinctive here, a gram
# like "the investment" survives the all-generic check (neither word alone
# is in _GENERIC_SUFFIX_WORDS or _QUERY_FRAMING_WORDS -- "the" is in
# neither) and still reaches the corpus with "investment" un-stripped,
# scoring against TATAINVEST's "tata investment" core almost as high as the
# bare word "investment" would have on its own. Confirmed this was the
# actual remaining gap: adding "investment" to _QUERY_FRAMING_WORDS alone
# did not fix "What is the investment outlook for Asian Paints?" until this
# was added too.
_STOPWORDS_FOR_GATE = {
    "the", "a", "an", "is", "are", "was", "were", "of", "for", "in", "on",
    "at", "to", "and", "or", "what", "how", "why", "when", "who", "this",
    "that", "with",
}

# Combined set used ONLY by _word_ngrams' gate check below (whether to try
# an n-gram at all) -- deliberately NOT used by _strip_generic, which must
# stay scoped to corporate-suffix words alone: broadening it to include
# _QUERY_FRAMING_WORDS/_STOPWORDS_FOR_GATE would also strip "investment"
# from TATAINVEST's OWN name when computing its corpus core (collapsing it
# to the bare word "tata", which Case C's owner-count check would then
# correctly-but-unhelpfully exclude as non-distinctive on ITS OWN account,
# breaking the "Tata Investment Corporation outlook" acceptance case).
_GATE_GENERIC_WORDS = _GENERIC_SUFFIX_WORDS | _QUERY_FRAMING_WORDS | _STOPWORDS_FOR_GATE


def _word_ngrams(text: str, max_len: int = 3) -> list[str]:
    """1-to-max_len contiguous word n-grams, longest-first (so a full 2-word
    company name is tried before its individual words, avoiding a spurious
    single-word match pre-empting a better multi-word one). An n-gram made
    ENTIRELY of generic suffix words is excluded regardless of length — not
    just the 1-word case. Found live: "Jio Financial Services" (after "jio"
    is stripped by the exact-match pass) leaves the residual 2-word gram
    "Financial Services", which fuzzy-matched a completely different real
    company ("HDB Financial Services Ltd") at a deceptively high ratio,
    since neither word is company-identifying on its own — the same failure
    mode _GENERIC_SUFFIX_WORDS already exists to prevent, just not yet
    generalized past n=1. A gram is only skipped when EVERY word in it is
    generic — "Jio Financial" (n=2, only "financial" generic) still passes.
    Step 3D — _GATE_GENERIC_WORDS (query-framing vocabulary + plain English
    function words) joins the same all-generic check, for the identical
    reason: "the investment outlook" (every word either a stopword or
    query-framing) is skipped, but "Tata Investment Corporation" (contains
    "tata", neither) still passes through and can fuzzy-match normally."""
    words = _WORD_RE.findall(text)
    words = [w for w in words if len(w) >= 3]
    grams: list[str] = []
    for n in range(max_len, 0, -1):
        for i in range(len(words) - n + 1):
            gram_words = words[i:i + n]
            if all(w.lower() in _GATE_GENERIC_WORDS for w in gram_words):
                continue
            grams.append(" ".join(gram_words))
    return grams


def _strip_generic(text: str) -> str:
    """Drops generic-suffix words before fuzzy comparison. Needed beyond
    _word_ngrams's whole-gram skip: found live that a gram like "buy
    Financial Services" (not all-generic — "buy" survives that filter)
    still fuzzy-matched a real company ("HDB Financial Services Ltd") at
    ratio 0.83, because difflib's SequenceMatcher scores on raw character
    overlap — a long shared generic suffix ("financial services") inflates
    the ratio almost independently of whether the differentiating word
    ("buy" vs "hdb") means anything at all. Stripping generic words from
    BOTH sides before scoring means the ratio reflects the part that
    actually identifies a company, not the boilerplate around it."""
    words = [w for w in _WORD_RE.findall(text) if w.lower() not in _GENERIC_SUFFIX_WORDS]
    return " ".join(words).lower()


def _fuzzy_candidates(token: str, cutoff: float, limit: int = 3) -> list[tuple[dict, float]]:
    if len(token) < 3:
        return []
    if token.lower() in _FUZZY_EXCLUDED_WORDS:
        return []
    token_core = _strip_generic(token)
    if len(token_core) < 3:
        return []
    # Step 3C, Case C, symmetric half — corpus-side exclusion of a
    # non-distinctive single word (see _corpus()'s comment) isn't enough on
    # its own: a compact no-space alias like "3mindia" is STILL close
    # enough (ratio 0.83, above cutoff) to the excluded word "india" that
    # keeping the alias itself in the corpus doesn't help. The query token
    # is the actual point of failure -- "India", named as a plain country
    # qualifier, should never become a fuzzy search key at all, regardless
    # of what happens to be sitting in the corpus. Same owner-count signal,
    # applied to the query side instead of just the corpus side.
    if " " not in token_core and _name_word_owner_counts().get(token_core, 0) >= _NON_DISTINCTIVE_MIN_OWNERS:
        return []
    corpus = _corpus()
    # Same reuse pattern stdlib's own difflib.get_close_matches uses: one
    # SequenceMatcher per token (not per comparison pair), with the token
    # fixed as the "b" side via set_seq2 — its b2j index (the expensive part
    # of a comparison) is then built exactly once per token and reused
    # across every corpus entry, instead of being rebuilt from scratch on
    # every single (token, entry) pair as the old `SequenceMatcher(a=...,
    # b=...)`-per-comparison version did. real_quick_ratio()/quick_ratio()
    # are cheap upper-bound checks — same pre-filter get_close_matches
    # applies before paying for the full ratio() computation.
    matcher = difflib.SequenceMatcher()
    matcher.set_seq2(token_core)
    scored: list[tuple[dict, float]] = []
    for text, text_core, co in corpus:
        matcher.set_seq1(text_core)
        if matcher.real_quick_ratio() < cutoff or matcher.quick_ratio() < cutoff:
            continue
        ratio = matcher.ratio()
        if ratio >= cutoff:
            scored.append((co, ratio))
    # Dedupe by symbol, keep the best-scoring alias match per company.
    best: dict[str, tuple[dict, float]] = {}
    for co, ratio in scored:
        sym = co["symbol"]
        if sym not in best or ratio > best[sym][1]:
            best[sym] = (co, ratio)
    return sorted(best.values(), key=lambda x: x[1], reverse=True)[:limit]


def extract_entities(query: str) -> dict:
    """Canonical entity extraction: exact/alias matches (V2's proven logic,
    reused verbatim) plus fuzzy-matched misspellings, deduplicated, resolved
    to real company rows — never a symbol that isn't genuinely in the NSE
    universe. Multi-company queries return every match, not just the first."""
    q_lower = query.lower()

    exact_symbols = _match_companies(q_lower)
    matches: list[dict] = []
    seen_symbols: set[str] = set()
    residual = query
    for sym in exact_symbols:
        co = next((c for c in _universe() if c["symbol"] == sym), None)
        if co and sym not in seen_symbols:
            matches.append({"symbol": sym, "name": co["name"], "match_type": "exact"})
            seen_symbols.add(sym)
            # Strip the matched alias text out of the residual query before
            # the fuzzy pass runs — otherwise an already-exact-matched phrase
            # like "PI Industries" (-> PIIND) gets re-scored by the fuzzy
            # pass and can spuriously also match a *different* company
            # sharing the same generic suffix word (e.g. "Page Industries").
            # Longest-first: found live that stripping a short alias first
            # (e.g. "uno") fragments a longer one that would otherwise have
            # matched whole (e.g. "uno minda"), leaving the bare remainder
            # word ("Minda") in the residual to spuriously fuzzy-match a
            # different real company (Minda Corporation Ltd) sharing that word.
            strip_candidates = sorted(
                {a for a in (co.get("aliases") or []) + [co["name"], co["symbol"]] if len(a) >= 3},
                key=len, reverse=True,
            )
            for alias in strip_candidates:
                residual = re.sub(re.escape(alias), " ", residual, flags=re.IGNORECASE)

    # Fuzzy pass — guards against misspellings like "Relaince" / "Infosis" /
    # "HDFC Bnak". Uses sliding 1-3 word n-grams over word-like tokens rather
    # than one greedy multi-word regex capture — a greedy capture swallows
    # trailing unrelated words (e.g. "Relaince Industries overvalued" as one
    # blob), which tanks the similarity ratio against the real company name
    # and silently misses the match. N-grams try every reasonable phrase
    # length so "Relaince Industries" gets scored on its own. Runs against
    # `residual` (query text minus anything already exactly matched above).
    for ngram in _word_ngrams(residual, max_len=3):
        token = ngram.lower()
        if token in seen_symbols or any(token == m["name"].lower() for m in matches):
            continue
        candidates = _fuzzy_candidates(token, _FUZZY_MATCH_CUTOFF, limit=1)
        for co, ratio in candidates:
            if co["symbol"] not in seen_symbols:
                matches.append({
                    "symbol": co["symbol"], "name": co["name"],
                    "match_type": "fuzzy", "matched_text": ngram, "confidence": round(ratio, 2),
                })
                seen_symbols.add(co["symbol"])

    sectors = [s for s in _SECTORS if _term_in_query(s, q_lower)]
    policies = [p for p in _POLICIES if _term_in_query(p, q_lower)]

    return {
        # kept as plain symbol list for backward compatibility with every
        # existing call site that reads entities["companies"] as list[str]
        "companies": [m["symbol"] for m in matches],
        "company_matches": matches,  # richer form — match_type/confidence for validation.py & UI badges
        "sectors": sectors,
        "policies": policies,
    }


def suggest_companies(query: str, limit: int = 3) -> list[dict]:
    """'Did you mean...' suggestions for a query that looks company-shaped
    but matched nothing real — used by the unrecognized-company response.
    Never returned as if they were real matches; always framed as a guess."""
    candidates: list[tuple[dict, float]] = []
    for ngram in _word_ngrams(query, max_len=3):
        candidates.extend(_fuzzy_candidates(ngram.lower(), _FUZZY_SUGGEST_CUTOFF, limit=limit))
    best: dict[str, float] = {}
    for co, ratio in candidates:
        if co["symbol"] not in best or ratio > best[co["symbol"]]:
            best[co["symbol"]] = ratio
    ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)[:limit]
    by_symbol = {c["symbol"]: c for c in _universe()}
    return [
        {"symbol": sym, "name": by_symbol[sym]["name"], "confidence": round(ratio, 2)}
        for sym, ratio in ranked if sym in by_symbol
    ]


def looks_like_unrecognized_company(query: str, entities: dict) -> bool:
    """Thin wrapper around this module's own _looks_like_unrecognized_company
    (P5 Stage 1: relocated here from ai_search_service.py, both pipelines now
    share this single definition instead of V3 importing V2's) against the
    new canonical entities dict — same behavior, new call site."""
    return _looks_like_unrecognized_company(query, entities)

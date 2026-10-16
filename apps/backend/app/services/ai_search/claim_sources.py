"""
Claim-level source IDs: validation.

The specialist prompts tag every piece of evidence with an ID (E events, N news, P policies, A announcements, C context lines; see EvidenceBundle.index()) and ask the model to list, for
each factual sentence of its answer, the IDs that support it ("claim_sources"). This module checks what comes back, deterministically, without a model:

  * structure          the entry has a claim string and a list of IDs
  * unknown_source     an ID that is not in the evidence index (the model invented it)
  * no_source          a claim with no ID at all
  * claim_not_in_answer the claim sentence does not appear in the generated answer (the model listed a sentence it never wrote)
  * ineligible_sources every cited item is something that cannot support this claim: a stock-tips article, a filing by another company for a sector claim, a brand-only mention for a
                       company claim (evidence_scope.py)
  * premise_unsupported the claim asserts the event the question assumed, and no evidence confirmed it
  * uncovered factual sentences in the answer that no claim entry covers

Non-blocking: the result is attached to the response (and read by the offline gate); it never rewrites or removes answer text. status: "not_provided" when the model returned no usable
claim_sources, "ok" when there is nothing to report, "problems" otherwise.
"""
from __future__ import annotations

import re

from app.services.ai_search import evidence_scope as scope
from app.services.ai_search.figures import _FISCAL

_FACT_RE = re.compile(r"\d|%|₹|\brs\.?\b|\bcrore\b|\bannounc|\bwon\b|\bwins?\b|\bsigned\b|\breported\b|\braised\b|\bdelivered\b|\bacquir|\bapproved\b|\blaunch|\bawarded\b|\bsecured\b|\bfiled\b|\bdisclosed\b|\binformed\b|\bdeclared\b|\bcompleted\b|\bentered into\b", re.IGNORECASE)
# A period label ("52-week", "1-day", "6-12 months") describes the window a statement covers; it is not a figure. It is removed before the digit test, so "52-week ranges only" is not a
# factual sentence, while "the 52-week high is 3350" still is (3350 remains). Deliberately narrow: nothing else is exempted, and a sentence with any other digit, %, rupee or event verb stays factual.
_PERIOD_LABEL = re.compile(r"(?<![\w.])\d+(?:\s*[-\u2013]\s*\d+)?[- ]?(?:week|day|month|year|quarter|hour|minute)s?(?![a-z])", re.IGNORECASE)


# Step 3.4G.2: factual-sentence detection is done per CLAUSE. A figure (digit, %, rupee, crore) makes a clause factual. An event verb makes a clause factual too, UNLESS the clause is an explicit statement
# about what the EVIDENCE does or does not contain ("The supplied evidence does not include credit-growth data...", "Credit growth was not reported in the supplied evidence"), or is the consequence
# clause of one ("..., so the reported strengthening cannot be assessed"). Generic negation is not enough: "The company did not report a profit" is itself a claim about the company and stays factual.
_FIGURE_RE = re.compile(r"\d|%|\u20b9|\brs\.?\b|\bcrore\b", re.IGNORECASE)
_EVENT_RE = re.compile(
    r"\bannounc|\bwon\b|\bwins?\b|\bsigned\b|\breported\b|\braised\b|\bdelivered\b|\bacquir|\bapproved\b|\blaunch|\bawarded\b|\bsecured\b|\bfiled\b|\bdisclosed\b|\binformed\b|\bdeclared\b"
    r"|\bcompleted\b|\bentered into\b|(?:did|does|do|has|have|had)\s+not\s+(?:report|announce|disclose|file|declare|post|deliver|win|sign|raise|launch|complete|approve|acquire|secure)\b"
    r"|\bnever\s+(?:report|announc|disclos|fil|declar)\w*", re.IGNORECASE)
_EV_NOUN = r"(?:(?:supplied|available|provided|current|retrieved|recent|this|the)\s+)*(?:evidence|data|information|coverage|context|sources?|material)"
_ABSENCE_FRAMES = (
    re.compile(_EV_NOUN + r"\b[^.;]{0,40}?\b(?:does|do|did)\s+not\s+(?:include|contain|show|establish|identify|provide|substantiate|confirm|cover|mention|say|report|explain|support|give|indicate|specify)\b", re.IGNORECASE),
    re.compile(_EV_NOUN + r"\b[^.;]{0,40}?\b(?:contains?|includes?|provides?|gives?|has|have|shows?)\s+(?:no|nothing)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:available|reported|included|provided|stated|shown|identified|covered|mentioned|established|disclosed)\s+in\s+(?:the\s+|this\s+)?(?:(?:supplied|available|current|provided|retrieved)\s+)*(?:evidence|data|context|sources?|material|coverage)\b", re.IGNORECASE),
    re.compile(_EV_NOUN + r"\b[^.;]{0,25}?\b(?:is|are)\s+(?:not\s+available|unavailable|absent|missing|insufficient)\b", re.IGNORECASE),
)
_INABILITY = re.compile(r"\bcannot\s+be\s+(?:established|assessed|determined|verified|confirmed|compared|quantified|evaluated)|\bcan(?:'|\u2019)?t\s+be\s+(?:established|assessed|determined)|\bcannot\s+(?:establish|assess|determine|verify|confirm|show|support)\b", re.IGNORECASE)
_CLAUSE_SPLIT = re.compile(r"(;|,\s*(?:but|and|while|so|therefore|thus|as)\b|\s+but\s+|\s+however,?\s+)", re.IGNORECASE)
_CAUSE_DELIM = re.compile(r",\s*(?:so|therefore|thus)\b", re.IGNORECASE)


def _is_absence_clause(clause: str) -> bool:
    return any(p.search(clause) for p in _ABSENCE_FRAMES)


# Step 3.4G.4. A clause is a LIMITATION about the evidence when it is an absence frame, or an inability statement that names the evidence ("cannot be established from the available evidence").
_EV_WORD = re.compile(r"(?<![a-z])(?:evidence|data|information|coverage|context|material|sources?)(?![a-z])", re.IGNORECASE)
# A pronoun continuation: "...cannot be established from the evidence; it does not include reported operating results." The pronoun refers to the evidence only when the previous clause was an
# evidence limitation AND the verb is present-tense negated ("does not"/"do not"): "it did not report a profit" or "it reported record profit" read as events and stay factual.
_PRONOUN_ABSENCE = re.compile(
    r"^\s*(?:it|this|these|they|which)\s+(?:does|do)\s+not\s+(?:include|contain|show|establish|identify|provide|substantiate|confirm|cover|mention|say|report|explain|support|give|indicate|specify)\b", re.IGNORECASE)


def _is_limitation_clause(clause: str) -> bool:
    return _is_absence_clause(clause) or (bool(_INABILITY.search(clause)) and bool(_EV_WORD.search(clause)))


def is_factual(sentence: str) -> bool:
    parts = _CLAUSE_SPLIT.split(sentence)
    prev_absence = False
    prev_limitation = False
    delim = ""
    for i, part in enumerate(parts):
        if i % 2 == 1:
            delim = part
            continue
        clause = _PERIOD_LABEL.sub(" ", part)
        pronoun_continuation = prev_limitation and bool(_PRONOUN_ABSENCE.match(part))
        absence = _is_absence_clause(part) or pronoun_continuation
        if absence or _is_limitation_clause(part):
            # inside an evidence limitation a fiscal label ("Q2", "FY27", "H1") describes the window the evidence does not cover; it is not a figure (same definition the figure validator uses)
            clause = _FISCAL.sub(" ", clause)
        if _FIGURE_RE.search(clause):
            return True
        if _EVENT_RE.search(clause):
            consequence_of_absence = prev_absence and bool(_CAUSE_DELIM.fullmatch(delim)) and bool(_INABILITY.search(part))
            if not absence and not consequence_of_absence:
                return True
        prev_absence = absence
        prev_limitation = absence or _is_limitation_clause(part)
    return False


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_ID_RE = re.compile(r"^[ENPAC]\d{1,3}$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9%₹.]+", " ", (text or "").lower()).strip().rstrip(".").strip()


def _field(d: dict, key: str):
    a = d.get("answer") if isinstance(d.get("answer"), dict) else {}
    return d.get(key) if d.get(key) not in (None, "") else a.get(key)


def answer_pieces(d: dict) -> list[str]:
    """The generated prose a user reads, from either the flat specialist output or the final response shape."""
    out: list[str] = []
    for k in ("summary", "bottom_line", "what_happened", "why_it_happened", "immediate_impact", "medium_term", "long_term", "what_priced_in"):
        v = _field(d, k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    for k in ("risks", "opportunities"):
        for x in _field(d, k) or []:
            if isinstance(x, str):
                out.append(x)
    for x in d.get("key_drivers") or []:
        if isinstance(x, dict):
            out.append(" ".join(str(x.get(k) or "") for k in ("title", "explanation")).strip())
    for c in d.get("companies") or []:
        if isinstance(c, dict) and c.get("reason"):
            out.append(str(c["reason"]))
    # Step 3.4G.1: sectors[].explanation is public model-written text. Every public factual surface must be inspectable by the same claim authorization.
    for s in d.get("sectors") or []:
        if isinstance(s, dict) and s.get("explanation"):
            out.append(str(s["explanation"]))
    de = d.get("decision_engine_v2") or {}
    if isinstance(de, dict) and de.get("why"):
        out.append(str(de["why"]))
    return [p for p in out if p.strip()]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split((text or "").replace("\n", " ")) if len(s.strip()) > 3]


_TOKEN_RE = re.compile(r"[a-z0-9%₹.]+")


def _tokens(text: str) -> set[str]:
    return {t.strip(".") for t in _TOKEN_RE.findall((text or "").lower()) if t.strip(".")}


# ── protected-attribute matching (ported from the offline investigation, 2026-10-16) ───────────────────────────────
# Layers under the original substring/Jaccard check above: entity/figure/direction/unit/period must agree
# whenever either side mentions one; negation and a small polarity/comparison-direction lexicon are checked
# as explicit vetoes; only once all of that agrees does a normalized-token fallback (symmetric Jaccard, or a
# directional "does the claim's own content fit inside the sentence" precision check) decide equivalence.
# Investigation: D:\IG-claims-repro\apps\backend\tests\services\test_ai_search_claim_matching_*.py,
# test_ai_search_directional_equivalence_investigation.py, test_ai_search_omission_and_year_classification_investigation.py.

_PERCENT_WORD_RE = re.compile(r"\b(?:percent|pct)\b", re.IGNORECASE)


def _unify_percent_wording(text: str) -> str:
    return _PERCENT_WORD_RE.sub("%", text or "")


_BARE_FIGURE_RE = re.compile(r"(?:\u20b9\s?)?\d[\d,]*(?:\.\d+)?\s?%?")


def _is_bare_year(token: str) -> bool:
    n = token.strip()
    return bool(re.fullmatch(r"\d{4}", n)) and 2000 <= int(n) <= 2035


def _normalize_figure_token(raw: str) -> str:
    cleaned = raw.replace(",", "").strip()
    has_rupee = cleaned.startswith("\u20b9")
    has_percent = cleaned.endswith("%")
    numeric = cleaned.strip("\u20b9% ").strip()
    try:
        value = float(numeric)
        numeric_canonical = ("%g" % value) if value == int(value) or "." in numeric else numeric
    except ValueError:
        numeric_canonical = numeric
    return ("\u20b9" if has_rupee else "") + numeric_canonical + ("%" if has_percent else "")


def _bare_years(text: str) -> set[str]:
    """A bare 4-digit token in the same year range production's figures.py already exempts from figure
    grounding (unsupported_figures()) is a PERIOD attribute, not a financial quantity -- reclassified here
    rather than merely dropped, so a genuine year change (2024 vs 2025) still counts as a mismatch."""
    return {f.strip() for f in _BARE_FIGURE_RE.findall(text) if f.strip() and _is_bare_year(f.strip())}


def _figures(text: str) -> set[str]:
    """Figure extraction with the bare-year exclusion: a bare 4-digit token in the recognized year range
    never becomes a "figure" requiring exact match (it is picked up separately by _bare_years, as a period)."""
    out = set()
    for f in _BARE_FIGURE_RE.findall(text):
        if not f.strip() or _is_bare_year(f.strip()):
            continue
        out.add(_normalize_figure_token(f))
    return out


_DIRECTION_LEXICON = {
    "positive": {"grew", "grow", "growth", "rose", "rise", "increased", "increase", "gained", "gain",
                 "expanded", "expansion", "improved", "improvement", "secured", "won", "up"},
    "negative": {"declined", "decline", "fell", "fall", "dropped", "drop", "shrank", "shrink",
                 "lagged", "lag", "worsened", "down", "lost", "loss"},
}
_DIRECTION_PHRASES = {
    "negative": [r"\btaken\b.{0,25}\blonger\b", r"\blonger\b.{0,40}\bwould\s+suggest\b", r"\bfallen\s+short\b",
                 r"\bbehind\s+schedule\b", r"\bunderperform"],
    "positive": [r"\bahead\s+of\s+schedule\b", r"\bexceeded\b", r"\bbeat\s+expectations\b", r"\boutperform"],
}
_COMPARATIVE_TERM_PATTERNS = (
    r"\boutperform\w*", r"\bunderperform\w*", r"\bbeat\b", r"\blagged\s+behind\b", r"\blag\s+behind\b",
    r"\bbest\b", r"\bworst\b", r"\bstrongest\b", r"\bweakest\b", r"\bleading\b", r"\blagging\b",
)


def _directions(text: str) -> set[str]:
    lowered = (text or "").lower()
    word_hits = {pole for pole, words in _DIRECTION_LEXICON.items() if any(re.search(rf"\b{w}\b", lowered) for w in words)}
    phrase_hits = {pole for pole, patterns in _DIRECTION_PHRASES.items() if any(re.search(p, lowered) for p in patterns)}
    return word_hits | phrase_hits


def _has_comparative_term(text: str) -> bool:
    low = (text or "").lower()
    return any(re.search(p, low) for p in _COMPARATIVE_TERM_PATTERNS)


_UNIT_RE = re.compile(r"\b(crore|lakh|million|billion)\b", re.IGNORECASE)
_PERIOD_RE = re.compile(r"\b(q[1-4]|fy\d{2,4}|h[12]|jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*|quarter|year)\b", re.IGNORECASE)


def _units(text: str) -> set[str]:
    return {u.lower() for u in _UNIT_RE.findall(text or "")}


def _periods(text: str) -> set[str]:
    return {p.lower() for p in _PERIOD_RE.findall(text or "")} | _bare_years(text)


def _company_terms_cache(companies: list[str], universe: list[dict]) -> dict[str, dict]:
    """Performance (2026-10-16 review): scope.company_terms() does a linear O(len(universe)) scan to find
    one company's row. similar() is called inside nested loops over claim_sources entries x prose
    sentences, and every call independently re-derives terms for every company in the comparison from
    _entities() AND (separately) from _comparison_relation() -- up to 4 redundant full-universe scans per
    similar() call, confirmed to cost ~75x longer per call at a realistic 600-company universe. Computed
    ONCE per validate_claim_sources() invocation (companies/universe don't change within one call) and
    threaded through as `terms_cache` instead."""
    return {sym: scope.company_terms(sym, universe) for sym in (companies or []) if sym}


def _entities(text: str, universe: list[dict], companies: list[str], terms_cache: dict[str, dict] | None = None) -> set[str]:
    """Universe-driven, not a hardcoded alias table: for every company symbol the comparison actually
    concerns (`entities["companies"]` from the pipeline's own entity resolution), checks whether this text
    names it via the SAME strong-name/symbol/alias resolver evidence_scope.py already uses for eligibility
    (`company_terms`/`names_company`). Generalizes to any company the universe knows, not just the pair a
    test corpus happened to use. `terms_cache`, when provided, avoids re-deriving company_terms() per call
    (see _company_terms_cache); falls back to computing it inline when absent, so standalone callers and
    tests are unaffected."""
    cache = terms_cache if terms_cache is not None else _company_terms_cache(companies, universe)
    hits = set()
    for symbol in companies or []:
        if not symbol:
            continue
        terms = cache.get(symbol) or scope.company_terms(symbol, universe)
        if scope.names_company(text, terms) == "strong":
            hits.add(symbol)
    return hits


_NEGATION_RE = re.compile(r"\b(not|no|never|without|fails? to|did not|didn't|does not|doesn't|hasn't|has not)\b", re.IGNORECASE)


def _is_negated(text: str) -> bool:
    return bool(_NEGATION_RE.search(text or ""))


_POLARITY_PAIRS: list[tuple[set[str], set[str]]] = [
    ({"best"}, {"worst"}),
    ({"highest"}, {"lowest"}),
    ({"strongest"}, {"weakest"}),
    ({"improved", "improving"}, {"deteriorated", "deteriorating", "worsened", "worsening"}),
    ({"outperform", "outperformed", "outperforming"}, {"underperform", "underperformed", "underperforming"}),
    ({"leading", "leader"}, {"lagging", "laggard"}),
]


def _polarity_poles(text: str) -> set[str]:
    lowered = (text or "").lower()
    poles: set[str] = set()
    for i, (high_words, low_words) in enumerate(_POLARITY_PAIRS):
        if any(re.search(rf"\b{w}\b", lowered) for w in high_words):
            poles.add(f"{i}:high")
        if any(re.search(rf"\b{w}\b", lowered) for w in low_words):
            poles.add(f"{i}:low")
    return poles


def _polarity_conflict(a: str, b: str) -> bool:
    pa, pb = _polarity_poles(a), _polarity_poles(b)
    for i in range(len(_POLARITY_PAIRS)):
        a_high, a_low = f"{i}:high" in pa, f"{i}:low" in pa
        b_high, b_low = f"{i}:high" in pb, f"{i}:low" in pb
        if (a_high and b_low) or (a_low and b_high):
            return True
    return False


_COMPARISON_VERB_WORDS = ("outperformed", "underperformed", "beat", "lagged behind", "led")
_COMPARISON_VERB_RE = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in _COMPARISON_VERB_WORDS) + r")\b", re.IGNORECASE)


def _comparison_relation(text: str, companies: list[str], universe: list[dict], terms_cache: dict[str, dict] | None = None) -> tuple[str, str, str] | None:
    """Locates (subject_symbol, verb, object_symbol) for a comparison sentence naming two of the companies
    this claim concerns, in the order they appear -- built from the SAME universe-driven resolver as
    _entities(), not a hardcoded symbol list, so it generalizes to any pair the comparison actually names.
    Shares `terms_cache` with _entities() -- see _company_terms_cache."""
    lowered = (text or "").lower()
    cache = terms_cache if terms_cache is not None else _company_terms_cache(companies, universe)
    terms_by_symbol = {sym: (cache.get(sym) or scope.company_terms(sym, universe)) for sym in (companies or []) if sym}
    mentions: list[tuple[int, str]] = []
    for sym, terms in terms_by_symbol.items():
        for s in terms.get("strong", []):
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", lowered):
                mentions.append((m.start(), sym))
    mentions.sort()
    if len(mentions) < 2:
        return None
    verb_match = _COMPARISON_VERB_RE.search(lowered)   # same lowered string the mention positions were found in -- keeps indices comparable
    if not verb_match:
        return None
    before = [m for m in mentions if m[0] < verb_match.start()]
    after = [m for m in mentions if m[0] > verb_match.start()]
    if not before or not after:
        return None
    return (before[-1][1], verb_match.group(0).lower(), after[0][1])


def _comparison_direction_conflict(a: str, b: str, companies: list[str], universe: list[dict], terms_cache: dict[str, dict] | None = None) -> bool:
    ra = _comparison_relation(a, companies, universe, terms_cache)
    rb = _comparison_relation(b, companies, universe, terms_cache)
    if ra is None or rb is None:
        return False
    (a_subj, a_verb, a_obj), (b_subj, b_verb, b_obj) = ra, rb
    return a_verb == b_verb and a_subj == b_obj and a_obj == b_subj and a_subj != a_obj


_STOPWORDS = {"a", "an", "the", "of", "in", "to", "for", "as", "has", "have", "had", "its", "by", "with", "was", "were", "this", "that", "and", "but"}
_SYNONYMS = {
    "rose": "grew", "increased": "grew", "expanded": "grew", "improved": "grew",
    "secured": "won", "reached": "reported", "worth": "of", "percent": "%",
}


def _normalized_tokens(text: str) -> set[str]:
    toks = _tokens(text) - _STOPWORDS
    return {_SYNONYMS.get(t, t) for t in toks}


def _normalized_jaccard(a: str, b: str, threshold: float) -> bool:
    na, nb = _norm(a), _norm(b)
    if na and nb and (na in nb or nb in na):
        return True
    ta, tb = _normalized_tokens(a), _normalized_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold


def _precision_ratio(sentence: str, claim: str) -> float:
    """Directional: what fraction of the CLAIM's own meaningful tokens are found in the sentence. A concise,
    accurate citation of a verbose sentence scores high here even when a symmetric Jaccard ratio would be
    diluted by the sentence's incidental padding; an unsupported extension (extra content the sentence never
    said) scores low, since its own unique tokens aren't found anywhere."""
    claim_tokens = _normalized_tokens(claim)
    if not claim_tokens:
        return 0.0
    sentence_tokens = _normalized_tokens(sentence)
    return len(claim_tokens & sentence_tokens) / len(claim_tokens)


_OMISSION_PRECISION_FLOOR = 0.75


def similar(a: str, b: str, universe: list[dict], entities: dict, jaccard_threshold: float = 0.35, cross_claim: bool = False, terms_cache: dict[str, dict] | None = None) -> bool:
    """True when two sentences are the same claim for our purposes. Checks, in order: entity/figure/
    direction identity (strict -- a mismatch here is never forgiven by lexical overlap elsewhere), then
    unit/period identity (an explicit conflict always rejects; an OMISSION on one side is tolerated only
    when the shorter text's own content is otherwise almost entirely contained in the other, so a concise
    citation can drop incidental detail without that becoming a way to smuggle in unsupported additions),
    then negation and a small polarity/comparison-direction veto, and only once all of that agrees does a
    normalized-token fallback decide equivalence.

    `cross_claim` distinguishes two genuinely different questions this function is asked, and they must NOT
    share the same tolerance: checking whether ONE specific claim_sources entry matches the sentence it is
    meant to cite (cross_claim=False, the model's own paraphrase of its own citation -- safe to recover via
    the lenient fallback) versus sweeping whether a factual sentence is covered by ANY claim_sources entry
    in general (cross_claim=True -- a restatement of an ALREADY-CITED fact in a different field must still
    get its own independent citation; "no fuzzy matching" across claims, confirmed as an existing,
    deliberate production invariant by test_ai_search_generation_contract.py's
    test_paraphrasing_a_claimed_fact_in_another_field_is_still_rejected_no_fuzzy_matching). Entity/figure/
    direction/unit/period/negation/polarity checks are identical either way -- only the final fallback's
    leniency differs: cross_claim uses the ORIGINAL, pre-existing threshold (0.7) and never the
    directional-precision shortcut; non-cross_claim uses the lenient fallback this investigation validated.
    `universe`/`entities` are the same values validate_claim_sources() already has in scope, needed here so
    entity resolution generalizes to any company the comparison concerns instead of a fixed pair.
    `terms_cache` (performance, 2026-10-16 review): validate_claim_sources() precomputes company_terms()
    ONCE per call and passes it in here, instead of every similar() call re-scanning the universe; falls
    back to computing it inline when absent, so standalone callers and tests are unaffected."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False

    companies = [c for c in (entities.get("companies") or []) if c]
    a_n, b_n = _unify_percent_wording(a), _unify_percent_wording(b)
    if terms_cache is None:
        terms_cache = _company_terms_cache(companies, universe)

    # Staged, cheapest-first (2026-10-16 performance review): each check is computed and evaluated before
    # the next is even run, instead of computing all three upfront -- _directions() alone accounts for
    # ~63% of this function's cost (it runs up to 31 regex searches), so skipping it whenever a cheaper
    # entity or figure mismatch already decides the outcome is a real win (confirmed ~3x faster on a
    # realistic 10-claim/15-sentence/600-company scenario) with ZERO behavior change (confirmed byte-
    # identical against the full v1-v3 hard-negative + legitimate-paraphrase regression corpus before this
    # reordering was applied). The logic of each check is unchanged -- only WHEN it runs.
    ea, eb = _entities(a_n, universe, companies, terms_cache), _entities(b_n, universe, companies, terms_cache)
    if (ea or eb) and ea != eb:
        return False
    fa, fb = _figures(a_n), _figures(b_n)
    if (fa or fb) and fa != fb:
        return False
    da, db = _directions(a_n), _directions(b_n)
    if (da or db) and da != db:
        return False

    claim_precision = _precision_ratio(a_n, b_n)
    ua, ub = _units(a_n), _units(b_n)
    pa, pb = _periods(a_n), _periods(b_n)
    for x, y in ((ua, ub), (pa, pb)):
        if x and y:
            if x != y:
                return False
        elif x != y:   # exactly one side has it -- an omission, tolerated only when precision is high
            if cross_claim or claim_precision < _OMISSION_PRECISION_FLOOR:
                return False

    if _is_negated(a_n) != _is_negated(b_n):
        return False
    if _polarity_conflict(a_n, b_n):
        return False
    if _comparison_direction_conflict(a_n, b_n, companies, universe, terms_cache):
        return False

    if cross_claim:
        return _normalized_jaccard(a_n, b_n, threshold=0.7)
    return _normalized_jaccard(a_n, b_n, threshold=jaccard_threshold) or claim_precision >= 0.8


def factual_sentences(answer: dict) -> list[str]:
    """Sentences of the generated prose that look like factual statements (a number, a currency amount, or an event verb)."""
    out: list[str] = []
    for p in answer_pieces(answer):
        for s in _sentences(p):
            if is_factual(s):
                out.append(s)
    return list(dict.fromkeys(out))


def _claim_scope(sentence: str, resolved: list[str], universe: list[dict], sectors: list[str]) -> tuple[str, str | None]:
    for sym in resolved:
        if scope.names_company(sentence, scope.company_terms(sym, universe)):
            return "company", sym
    low = sentence.lower()
    if any(s.lower() in low for s in sectors) or re.search(r"\b(?:sector|industry|it services|banking|banks|lenders)\b", low):
        return "sector", None
    return "market", None


def validate_claim_sources(raw, index: list[dict], answer: dict, entities: dict, universe: list[dict], premise: dict | None = None) -> dict:
    by_id = {e["id"]: e for e in index}
    resolved = [c for c in (entities.get("companies") or []) if c]
    sectors = entities.get("sectors") or []
    pieces = answer_pieces(answer)
    haystack = _norm(" ".join(pieces))
    # Performance (2026-10-16 review): companies/universe are fixed for this whole call -- compute
    # company_terms() ONCE here instead of letting every similar() call (there can be many, inside the
    # claim_not_in_answer and uncovered-sweep loops below) re-scan the universe independently.
    terms_cache = _company_terms_cache(resolved, universe)

    if not isinstance(raw, list) or not raw:
        return {"status": "not_provided", "claims": [], "summary": {"claims": 0, "ok": 0, "problems": 0, "uncovered_factual_sentences": None}, "uncovered": []}

    claims_out: list[dict] = []
    for entry in raw:
        problems: list[str] = []
        claim = entry.get("claim") if isinstance(entry, dict) else None
        sources = entry.get("sources") if isinstance(entry, dict) else None
        if not isinstance(claim, str) or not claim.strip() or not isinstance(sources, list):
            claims_out.append({"claim": str(claim)[:200] if claim else "", "sources": [], "status": "malformed", "problems": ["malformed entry (needs a claim string and a sources list)"]})
            continue
        ids = [str(s).strip().strip("[]").upper() for s in sources if str(s).strip()]
        known = [i for i in ids if i in by_id]
        unknown = [i for i in ids if i not in by_id]
        if not ids:
            problems.append("no_source")
        if unknown:
            problems.append(f"unknown_source: {', '.join(unknown)}")
        # Explicit policy (2026-10-16 review): self-consistency, not evidence authorization -- this asks
        # "did the model write something close to its OWN claim_sources[].claim text anywhere in its own
        # prose," not "does this entry grant coverage to some other sentence." cross_claim=False (the
        # lenient fallback) is deliberate here: a paraphrase between what the model put in claim_sources
        # and what it actually wrote is not a safety-relevant gap the way cross-field evidence coverage is.
        # Never change this to cross_claim=True without re-testing: this is NOT the "no fuzzy matching
        # across claims" gate -- that is the separate uncovered-sentence sweep below, which stays strict.
        if _norm(claim) and not any(similar(claim, s, universe, entities, cross_claim=False, terms_cache=terms_cache) for p in pieces for s in _sentences(p)) and _norm(claim) not in haystack:
            problems.append("claim_not_in_answer")
        sc, sym = _claim_scope(claim, resolved, universe, sectors)
        verdicts = []
        for i in known:
            e = by_id[i]
            item = {"kind": e["kind"], "title": e.get("title") or "", "summary": e.get("summary") or "", "companies": e.get("companies") or []}
            if e["kind"] == "context":
                verdicts.append((i, True, "context line"))
            elif sc == "company":
                ok, why = scope.eligible_for_company(item, sym, universe)
                verdicts.append((i, ok, why))
            elif sc == "sector":
                ok, why = scope.eligible_for_sector(item)
                verdicts.append((i, ok, why))
            else:
                ok = not scope.is_tips_article(item["title"], item["summary"]) and not scope.is_single_company_filing(item["title"])
                verdicts.append((i, ok, "market claim" if ok else "tips article or single-company filing"))
        if known and not any(ok for _i, ok, _w in verdicts):
            problems.append("ineligible_sources: " + "; ".join(f"{i} ({why})" for i, _ok, why in verdicts))
        if premise and premise.get("required") and not premise.get("supported"):
            pg = scope.premise_groups("just " + " ".join(premise.get("terms") or []))
            if sym and pg and any(scope._has_term(claim, t) for g in pg for t in g):
                problems.append("premise_unsupported: the question's event was not confirmed by any retrieved evidence")
        claims_out.append({"claim": claim.strip()[:300], "sources": ids, "scope": sc, "company": sym, "status": "ok" if not problems else "problem", "problems": problems,
                           "ineligible": [i for i, ok, _w in verdicts if not ok]})

    # Explicit policy (2026-10-16 review): evidence authorization, not self-consistency -- this asks "does
    # ANY claim_sources entry grant coverage to this factual sentence." cross_claim=True (strict, no
    # omission tolerance, no precision shortcut) is deliberate and load-bearing: a restatement of an
    # already-cited fact in a different field must still get its own independent citation ("no fuzzy
    # matching across claims" -- test_ai_search_generation_contract.py's
    # test_paraphrasing_a_claimed_fact_in_another_field_is_still_rejected_no_fuzzy_matching). Never change
    # this to cross_claim=False: that reopens the confirmed regression this policy fixes.
    claim_texts = [c["claim"] for c in claims_out]
    uncovered = []
    for p in pieces:
        for s in _sentences(p):
            if is_factual(s) and not any(similar(s, c, universe, entities, cross_claim=True, terms_cache=terms_cache) for c in claim_texts):
                uncovered.append(s[:200])
    uncovered = list(dict.fromkeys(uncovered))
    n_ok = sum(1 for c in claims_out if c["status"] == "ok")
    n_bad = len(claims_out) - n_ok
    status = "ok" if (n_bad == 0 and not uncovered) else "problems"
    return {"status": status, "claims": claims_out, "uncovered": uncovered[:10],
            "summary": {"claims": len(claims_out), "ok": n_ok, "problems": n_bad, "uncovered_factual_sentences": len(uncovered)}}


def compact_index(index: list[dict]) -> list[dict]:
    """The evidence index as shipped in the response: enough to resolve any ID in claim_sources."""
    return [{k: e.get(k) for k in ("id", "kind", "title", "date", "source", "companies")} for e in index]

"""
Cross-source near-duplicate filter for news ingestion.

Why: the same real story arrives from several publishers (ET, Mint, NDTV Profit, Moneycontrol...) as independent rows with different ids and differently worded headlines. Id-based dedup
(BaseProvider / _persist_articles) cannot see that, and nothing downstream can collapse them afterwards (see the RSS cross-source dedup note: this was the hard gate before adding feeds).

Design: conservative on purpose. A false "duplicate" drops a legitimate second-source story; a missed duplicate is only the status quo. So an item is dropped only when a headline from a
DIFFERENT source, published within the recent window, matches strongly:
  - both headlines are reduced to a set of content tokens (lower-case, punctuation and stopwords removed, trailing publisher names removed, light plural stemming, numbers kept), and
  - Jaccard similarity >= 0.6 AND at least 4 shared tokens, OR the shorter headline is >= 85% contained in the longer one with >= 5 shared tokens (headlines of 6 tokens or fewer need Jaccard >= 0.8), and
  - when BOTH headlines carry numbers, the numbers must agree (a "profit up 12%" story is not a duplicate of a "profit up 15%" story, and a daily market wrap with different index levels is not
    a duplicate of yesterday's).
Same-source repeats are not handled here (id dedup already covers them).
"""
from __future__ import annotations

import re

_STOP = frozenset(
    "a an and are as at be by for from has have in into is it its of on or over that the their this to was were will with after amid says said say as per vs "
    "today live latest update updates news how what why when who which will may could should would here check".split()
)
_PUBLISHER_TAIL = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")     # "Headline - Economic Times", "Headline | Mint"
_NUM = re.compile(r"\d[\d,]*\.?\d*")
_WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def _stem(w: str) -> str:
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w


def fingerprint(headline: str) -> tuple[frozenset, frozenset]:
    """(content tokens, number tokens) for a headline."""
    h = _PUBLISHER_TAIL.sub("", (headline or "").strip()).lower().replace("&", " and ")
    nums = frozenset(n.replace(",", "").rstrip(".") for n in _NUM.findall(h))
    toks = frozenset(_stem(w) for w in _WORD.findall(h.replace(",", "")) if w not in _STOP and (len(w) >= 3 or w.isdigit()))
    return toks, nums


def is_duplicate(a: tuple[frozenset, frozenset], b: tuple[frozenset, frozenset]) -> bool:
    ta, na = a
    tb, nb = b
    if not ta or not tb:
        return False
    shared = ta & tb
    if len(shared) < 4:
        return False
    if na and nb and not (na & nb):
        return False                         # both quote figures and none match: different story
    jac = len(shared) / len(ta | tb)
    if min(len(ta), len(tb)) <= 6:
        return jac >= 0.8                    # short headlines differ by a single company name ("HDFC Bank ... dividend" vs "ICICI Bank ... dividend"): near-identical wording only
    contained = len(shared) / min(len(ta), len(tb))
    return jac >= 0.6 or (contained >= 0.85 and len(shared) >= 5)


def drop_cross_source_duplicates(items: list, recent: list[tuple[str, tuple[frozenset, frozenset]]]) -> tuple[list, list]:
    """items: RawItem-like objects with .headline and .source. recent: [(source, fingerprint)] already stored in the window.
    Returns (kept, dropped). Items within the same batch also count against each other (first one wins)."""
    kept, dropped = [], []
    pool = list(recent)
    for it in items:
        fp = fingerprint(it.headline)
        dup = next((s for s, other in pool if s != it.source and is_duplicate(fp, other)), None)
        if dup is not None:
            dropped.append((it, dup))
            continue
        kept.append(it)
        pool.append((it.source, fp))
    return kept, dropped

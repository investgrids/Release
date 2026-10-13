"""'What moved the market', investor implications, next-session scenarios and the investor takeaway for the Daily Brief.

Pure functions: no network, no DB, no LLM. Everything is derived from data the brief already holds (triaged events, verified sector and
index/FX moves, the deterministic opening signals, the economic calendar) and every claim carries its evidence label.

What this module never does:
  * it never says a development CAUSED a move because they happened on the same day. 'Confirmed' needs an authoritative source, a source
    headline that itself ties the development to the move, and a verified move in the matching market variable. Everything else with a
    verified same-session move is a 'potential contributor' and says plainly that timing alone does not show cause;
  * it never shows an impact score, direction or confidence for a development (the internal ranking key is not exposed);
  * it never connects a company to a development unless the event names it, and then only as 'mentioned';
  * it never invents probabilities, targets, support/resistance or expected ranges for the scenarios.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.services.daily_brief_composer import FLAT_PCT, NEAR_FLAT_PCT, parse_pct
from app.services.ingestion_dedup import fingerprint, is_duplicate

CONFIRMED, POTENTIAL, COMMENTARY = "confirmed_driver", "potential_contributor", "commentary"
MAX_ITEMS = 5
MAX_COMMENTARY = 1

# ── event hygiene ───────────────────────────────────────────────────────────────────────────────────────────────────

_COMMENTARY_MARKERS = (
    "analysis", "opinion", "explained", "outlook", "what to expect", "what to watch", "stocks to watch", "stocks to buy", "top picks",
    "target price", "brokerage", "should you", "can ", "could ", "may ", "might ", "likely to", "expected to", "view:", "preview", "decoded", "explainer",
)
_MOVE_UP = ("rise", "rises", "rose", "gain", "gains", "gained", "surge", "surges", "surged", "jump", "jumps", "jumped", "higher", "rally", "rallies",
            "strengthen", "strengthens", "firm", "firms", "climb", "climbs", "advance", "advances")
_MOVE_DOWN = ("fall", "falls", "fell", "drop", "drops", "dropped", "slump", "slumps", "slumped", "lower", "decline", "declines", "declined",
              "slide", "slides", "slid", "weaken", "weakens", "tumble", "tumbles", "sink", "sinks", "plunge", "plunges", "worst day")
_CAUSAL = re.compile(r"\b(on|after|as|amid|following|due to|because of|spark|sparks|sparked|trigger|triggers|triggered)\b", re.I)
_AUTHORITATIVE_ORIGINS = ("rbi", "reserve bank", "sebi", "nse", "bse", "ministry", "government", "pib", "fed", "ecb", "imf", "world bank", "mospi")
_MARKET_WIDE_WORDS = ("nifty", "sensex", "market", "rupee", "bond", "yield", "repo", "rate", "inflation", "crude", "oil", "fii", "fpi", "gdp",
                      "budget", "tariff", "policy", "liquidity", "vix", "dollar")

# Event sector names vs the sector index names the brief shows. Only aliases that really are the same sector.
_SECTOR_ALIASES = {
    "it": {"it", "information technology", "technology", "software", "it services"},
    "banking": {"banking", "banks", "bank", "financials", "financial services", "finance"},
    "private bank": {"private bank", "private banks"},
    "psu bank": {"psu bank", "psu banks", "public sector banks"},
    "pharma": {"pharma", "pharmaceuticals", "healthcare", "pharmaceutical"},
    "auto": {"auto", "automobile", "automobiles", "automotive"},
    "fmcg": {"fmcg", "consumer goods", "consumer staples"},
    "energy": {"energy", "oil & gas", "oil and gas", "power"},
    "metal": {"metal", "metals", "mining", "steel"},
    "realty": {"realty", "real estate"},
    "infra": {"infra", "infrastructure", "construction", "capital goods"},
}


def _canon_sector(name: str) -> str | None:
    n = re.sub(r"\s+", " ", (name or "").strip().lower())
    for canon, aliases in _SECTOR_ALIASES.items():
        if n in aliases:
            return canon
    return None


def sector_moves(sectors: list[dict] | None) -> dict[str, tuple[str, float]]:
    """canonical sector -> (display name, verified pct), from the sector index rows the brief already holds."""
    out: dict[str, tuple[str, float]] = {}
    for s in sectors or []:
        pct = parse_pct(s.get("value"))
        canon = _canon_sector(s.get("name") or "")
        if pct is not None and canon:
            out[canon] = (s["name"], pct)
    return out


def _ts(e: dict) -> datetime | None:
    raw = e.get("published_at") or e.get("triaged_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_commentary(e: dict) -> bool:
    h = (e.get("headline") or "").lower()
    return h.endswith("?") or any(m in h for m in _COMMENTARY_MARKERS)


def _authoritative(e: dict) -> bool:
    origin = (e.get("origin") or "").lower()
    return e.get("source") == "policy" or any(a in origin for a in _AUTHORITATIVE_ORIGINS)


def _market_wide(e: dict) -> bool:
    h = (e.get("headline") or "").lower()
    return e.get("source") == "policy" or any(re.search(rf"\b{re.escape(w)}", h) for w in _MARKET_WIDE_WORDS) or len(e.get("sectors") or []) >= 3


# ── dedup ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def cluster_events(events: list[dict]) -> list[list[dict]]:
    """Group events that cover the same underlying development: the same event id, or near-identical headlines (same token-set test
    the ingestion filter uses), regardless of outlet. Order inside a cluster: earliest first, so the original report leads."""
    clusters: list[tuple[tuple, list[dict]]] = []
    seen_ids: dict[str, int] = {}
    for e in sorted(events, key=lambda x: _ts(x) or datetime.min.replace(tzinfo=timezone.utc)):
        eid = e.get("id")
        if eid and eid in seen_ids:
            clusters[seen_ids[eid]][1].append(e)
            continue
        fp = fingerprint(e.get("headline") or "")
        for i, (cfp, members) in enumerate(clusters):
            if is_duplicate(fp, cfp):
                members.append(e)
                if eid:
                    seen_ids[eid] = i
                break
        else:
            clusters.append((fp, [e]))
            if eid:
                seen_ids[eid] = len(clusters) - 1
    return [members for _, members in clusters]


_GENERIC_TOKENS = frozenset(
    "market markets stock stocks share shares india indian sensex nifty day week year month months six one two three four five new first last "
    "rise rises fall falls higher lower open opens close closes sharpest worst best big key top high low".split()
)
_TOPIC_ANCHORS = frozenset("rbi sebi fed ecb imf opec budget gst tariff tariffs repo".split())
_RELATED_WINDOW = timedelta(hours=6)


def _topic_tokens(headline: str) -> frozenset:
    tokens, _numbers = fingerprint(headline)
    return frozenset(t for t in tokens if t not in _GENERIC_TOKENS and not t.isdigit())


def _related(a: list[dict], b: list[dict]) -> bool:
    """Two clusters are the same development seen from different angles when their lead headlines share at least three distinctive
    words, or two when one of them is a named authority/policy anchor (RBI, SEBI, Fed...), and they were reported within six hours."""
    ta, tb = _ts(a[0]), _ts(b[0])
    if ta and tb and abs(ta - tb) > _RELATED_WINDOW:
        return False
    shared = _topic_tokens(a[0].get("headline") or "") & _topic_tokens(b[0].get("headline") or "")
    return len(shared) >= 3 or (len(shared) >= 2 and bool(shared & _TOPIC_ANCHORS))


def merge_related(clusters: list[list[dict]]) -> list[list[dict]]:
    """Union clusters that are the same development seen from different angles, so one story does not take several of the five slots."""
    parent = list(range(len(clusters)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            if find(i) != find(j) and _related(clusters[i], clusters[j]):
                parent[find(j)] = find(i)
    merged: dict[int, list[dict]] = {}
    for i, members in enumerate(clusters):
        merged.setdefault(find(i), []).extend(members)
    return list(merged.values())


# ── matching a development to verified data ───────────────────────────────────────────────────────────────────────

def _headline_direction(headline: str) -> int:
    h = (headline or "").lower()
    up = any(re.search(rf"\b{w}\b", h) for w in _MOVE_UP)
    down = any(re.search(rf"\b{w}\b", h) for w in _MOVE_DOWN)
    return 1 if up and not down else -1 if down and not up else 0


def _variable_moves(facts: list[dict], snapshot: dict) -> dict[str, tuple[str, float]]:
    """market variable -> (label, verified pct move): the indices and the fact-registry signals the brief already verified."""
    out: dict[str, tuple[str, float]] = {}
    for key, label in (("nifty", "Nifty 50"), ("sensex", "Sensex"), ("banknifty", "Bank Nifty")):
        q = snapshot.get(key) or {}
        if q.get("value") not in (None, "", "—") and isinstance(q.get("pct"), (int, float)):
            out["market" if key == "nifty" else key] = (label, float(q["pct"]))
    for f in facts:
        pct = f.get("change_pct") if f.get("change_pct") is not None else f.get("numeric_value") if f.get("entity_type") == "market_index" else None
        if f.get("entity_key") == "BRENT_CRUDE":
            d = (f.get("direction") or "").lower()
            out["crude"] = ("Brent crude", (1.0 if d in ("rising", "up") else -1.0 if d in ("falling", "down") else 0.0))
        elif f.get("entity_key") == "USD_INR":
            d = (f.get("direction") or "").lower()
            out["rupee"] = ("USD/INR", (1.0 if d == "up" else -1.0 if d == "down" else 0.0))
        elif f.get("entity_key") == "INDIA_VIX" and isinstance(pct, (int, float)):
            out["vix"] = ("India VIX", float(pct))
    return out


def _matching_variable(headline: str, variables: dict[str, tuple[str, float]]) -> tuple[str, str, float, int] | None:
    """(key, label, move, expected_sign): the verified variable the headline's own move words refer to, with the sign that variable
    should show if the headline is right (rupee 'higher' means USD/INR lower)."""
    h = (headline or "").lower()
    direction = _headline_direction(headline)
    if direction == 0:
        return None
    table = (("rupee", "rupee", -1), ("crude", "crude", 1), ("oil", "crude", 1), ("nifty", "market", 1), ("sensex", "sensex", 1), ("bank nifty", "banknifty", 1),
             ("vix", "vix", 1), ("market", "market", 1))
    for word, key, sign in table:
        if re.search(rf"\b{word}\b", h) and key in variables:
            label, move = variables[key]
            return key, label, move, direction * sign
    return None


def _describe_move(name: str, move: float) -> str:
    """'-1.30%' for percent moves; 'higher'/'lower' for the direction-only variables (USD/INR, Brent)."""
    if name in ("USD/INR", "Brent crude"):
        return "higher" if move > 0 else "lower"
    return _fmt_pct(move)


def _consistent(match: tuple[str, str, float, int] | None) -> bool:
    """True when the verified variable moved the way the headline says it did. Rupee and crude carry only a direction (+1/-1); the
    others carry a percent move and must clear the flat threshold."""
    if not match:
        return False
    key, _label, move, expected = match
    if move == 0:
        return False
    if key not in ("rupee", "crude") and abs(move) < NEAR_FLAT_PCT:
        return False
    return (move > 0) == (expected > 0)


def _sector_hits(e: dict, smoves: dict[str, tuple[str, float]]) -> list[tuple[str, float | None]]:
    """The event's sectors, each with its verified same-session move when a sector index exists for it."""
    out = []
    for s in e.get("sectors") or []:
        canon = _canon_sector(s)
        if canon and canon in smoves:
            out.append((smoves[canon][0], smoves[canon][1]))
        else:
            out.append((str(s), None))
    return out


# ── ranking ─────────────────────────────────────────────────────────────────────────────────────────────────────────

_TIER_POINTS = {"Critical": 1.0, "High": 0.75, "Medium": 0.4, "Low": 0.1}


def _rank_key(e: dict, now: datetime, hits: list[tuple[str, float | None]], moved_variable: bool) -> float:
    """Internal sort key only; never exposed. relevance (tier) + freshness + significance + scope + observed reaction."""
    tier = _TIER_POINTS.get(e.get("priority_tier"), 0.1)
    ts = _ts(e)
    age_h = max(0.0, (now - ts).total_seconds() / 3600) if ts else 48.0
    fresh = max(0.0, 1 - age_h / 36)
    sig = min(1.0, (float(e.get("importance") or 0) / 10) * 0.7 + (0.3 if e.get("is_structural") else 0.0))
    scope = 1.0 if _market_wide(e) else (0.5 if len(e.get("sectors") or []) >= 1 else 0.2)
    reaction = 1.0 if moved_variable else (0.6 if any(m is not None and abs(m) >= FLAT_PCT for _, m in hits) else 0.0)
    return 0.35 * tier + 0.15 * fresh + 0.15 * sig + 0.15 * scope + 0.20 * reaction


# ── what moved the market ───────────────────────────────────────────────────────────────────────────────────────────

def _fmt_pct(p: float) -> str:
    return f"{p:+.2f}%"


def build_market_drivers(events: list[dict], *, snapshot: dict, facts: list[dict], now: datetime, event_meta: dict[str, dict] | None = None,
                         article_links: dict[str, str] | None = None) -> dict:
    """Up to five developments, deduplicated, ranked, and labelled by how strong the evidence is. Fewer than five is normal."""
    event_meta, article_links = event_meta or {}, article_links or {}
    smoves = sector_moves(snapshot.get("sectors"))
    variables = _variable_moves(facts, snapshot)
    scored: list[tuple[float, dict]] = []

    for members in merge_related(cluster_events([e for e in events if e.get("headline")])):
        # lead = the most important report of the development (highest tier/importance), ties to the earliest
        lead = max(members, key=lambda m: (_TIER_POINTS.get(m.get("priority_tier"), 0.1), float(m.get("importance") or 0), -(_ts(m) or now).timestamp()))
        hits = _sector_hits(lead, smoves)
        match = _matching_variable(lead["headline"], variables)
        consistent = _consistent(match)
        reasons: list[str] = []
        if is_commentary(lead):
            label = COMMENTARY
        elif _authoritative(lead) and _CAUSAL.search(lead["headline"]) and consistent:
            label = CONFIRMED
            reasons.append(f"The source itself ties this development to the move, and the verified data agrees: {match[1]} {'higher' if match[2] > 0 else 'lower'}.")
        elif _market_wide(lead) or lead.get("priority_tier") == "Critical" or any(m is not None and abs(m) >= FLAT_PCT for _, m in hits):
            # A potential contributor is broad (market-wide), top priority, or tied to a sector whose verified index moved. A single-company
            # result or notice (for example one company's quarterly profit) is not offered as a reason the market moved.
            label = POTENTIAL
        else:
            continue                                    # not broad or significant enough to be a market development

        if label == POTENTIAL:
            moved = [(n, m) for n, m in hits if m is not None and abs(m) >= FLAT_PCT]
            if match and match[0] in ("rupee", "crude"):
                moved.append((match[1], match[2]))
            if moved:
                shown = ", ".join(f"{n} {_describe_move(n, m)}" for n, m in moved[:2])
                reasons.append(f"Coincided with {shown} in the same session. Timing alone does not show that this caused the move.")
            else:
                reasons.append("A significant development of the period; no verified same-session move in an exposed sector is available to compare it with.")
        if label == COMMENTARY:
            reasons.append("Analysis or opinion rather than a reported fact; shown for context, not as a driver.")
        tier = lead.get("priority_tier")
        if tier in ("Critical", "High") and label != COMMENTARY:
            reasons.append(f"MarketRipple's event scoring rates it {tier} priority.")
        if len(members) > 1:
            reasons.append(f"Covered in {len(members)} articles from {len({m.get('origin') or m.get('source') for m in members})} source(s), including other angles on the same development; shown once.")

        meta = event_meta.get(lead.get("id") or "", {})
        named = [str(t).upper().split(".")[0] for t in list(lead.get("tickers") or []) + list(meta.get("companies") or []) if t]
        ts = _ts({"published_at": meta.get("published_at")}) or _ts(lead)
        item = {
            "id": lead.get("id"),
            "headline": (meta.get("title") or lead["headline"]).strip(),
            "source": meta.get("source") or lead.get("origin") or None,
            "published_at": ts.isoformat() if ts else None,
            "evidence_label": label,
            "relevance": reasons,
            "sectors": [{"name": n, "verified_move_pct": m} for n, m in hits[:4]],
            "companies": [{"symbol": sym, "relation": "mentioned"} for sym in dict.fromkeys(named)][:4],
            "articles_merged": len(members),
            "links": {
                "event": f"/events/{meta.get('slug') or lead.get('id')}" if lead.get("id") else None,
                "article": article_links.get(lead.get("id") or ""),
            },
        }
        scored.append((_rank_key(lead, now, hits, consistent), item))

    scored.sort(key=lambda t: t[0], reverse=True)
    rank_label = {CONFIRMED: 0, POTENTIAL: 1, COMMENTARY: 2}
    picked, commentary_used = [], 0
    for _, it in sorted(scored, key=lambda t: (rank_label[t[1]["evidence_label"]], -t[0])):
        if len(picked) >= MAX_ITEMS:
            break
        if it["evidence_label"] == COMMENTARY:
            if commentary_used >= MAX_COMMENTARY:
                continue
            commentary_used += 1
        picked.append(it)

    groups = {CONFIRMED: [], POTENTIAL: [], COMMENTARY: []}
    for it in picked:
        groups[it["evidence_label"]].append(it)
    note = None
    if not picked:
        note = "No development met the evidence threshold for this session."
    elif len(picked) < MAX_ITEMS:
        note = f"{len(picked)} development{'s' if len(picked) != 1 else ''} met the evidence threshold; nothing was added to fill the space."
    return {"items": picked, "groups": groups, "note": note, "considered": len(events),
            "method": "Deduplicated and ranked by relevance, freshness, significance, scope and verified same-session moves. Labels describe the evidence, not certainty of cause."}


# ── investor implications ───────────────────────────────────────────────────────────────────────────────────────────

def build_implications(drivers: dict) -> dict:
    """Sectors worth attention, each tied to the developments that name it and to a verified move where one exists. Companies appear only
    as 'mentioned'. No recommendation, no direction."""
    by_sector: dict[str, dict] = {}
    for it in drivers.get("items", []):
        if it["evidence_label"] == COMMENTARY:
            continue
        for s in it["sectors"]:
            row = by_sector.setdefault(s["name"], {"sector": s["name"], "verified_move_pct": s["verified_move_pct"], "developments": [], "companies_mentioned": []})
            row["developments"].append({"id": it["id"], "headline": it["headline"], "evidence_label": it["evidence_label"]})
            for c in it["companies"]:
                if c["symbol"] not in row["companies_mentioned"]:
                    row["companies_mentioned"].append(c["symbol"])
    rows = sorted(by_sector.values(), key=lambda r: (-sum(d["evidence_label"] == CONFIRMED for d in r["developments"]), -len(r["developments"])))[:4]
    for r in rows:
        n = len(r["developments"])
        move = f" Its sector index moved {_fmt_pct(r['verified_move_pct'])} in the session." if r["verified_move_pct"] is not None else " No verified sector index move is available."
        r["why"] = f"Named in {n} development{'s' if n != 1 else ''} above.{move}"
        r["companies_label"] = "Mentioned in these developments (not an assessment of impact)" if r["companies_mentioned"] else None
    return {"items": rows, "note": None if rows else "No sector is tied to a verified development yet."}


# ── next-session scenarios ─────────────────────────────────────────────────────────────────────────────────────────

_TITLES = {
    "Negative": ("Recovery scenario", "Mixed / range-bound scenario", "Selling-pressure scenario"),
    "Positive": ("Continuation scenario", "Mixed / range-bound scenario", "Pullback scenario"),
}
_DEFAULT_TITLES = ("Upside scenario", "Mixed / range-bound scenario", "Downside scenario")


def _row(rows: list[dict], prefix: str) -> dict | None:
    return next((r for r in rows if (r.get("label") or "").lower().startswith(prefix.lower())), None)


def _gift_move(row: dict | None) -> float | None:
    return parse_pct(row.get("value")) if row else None


def _setup(rows: list[dict]) -> dict:
    """A plain description of how the overnight signals line up. No lean is declared when they disagree."""
    directional = [r for r in rows if r.get("direction") in ("positive", "negative", "neutral")]
    pos = [r for r in directional if r["direction"] == "positive"]
    neg = [r for r in directional if r["direction"] == "negative"]
    if pos and neg:
        title = "Mixed overnight setup"
    elif len(pos) >= 2 and not neg:
        title = "Positive overnight setup"
    elif len(neg) >= 2 and not pos:
        title = "Negative overnight setup"
    else:
        title = "Flat overnight setup"

    parts: list[str] = []
    gift, fut, breadth, fii, vix = _row(rows, "GIFT"), next((r for r in rows if "fut" in (r.get("label") or "").lower()), None), _row(rows, "Global"), _row(rows, "FII"), _row(rows, "India VIX")
    gm = _gift_move(gift)
    if gift and gift["direction"] != "contextual":
        mild = "mildly " if gm is not None and abs(gm) < 0.5 else ""
        parts.append(f"GIFT Nifty indicates a {mild}{'positive' if gift['direction'] == 'positive' else 'negative' if gift['direction'] == 'negative' else 'flat'} start")
    if fut:
        word = {"positive": "higher", "negative": "lower"}.get(fut["direction"], "flat")
        parts.append(f"US futures are {word}")
    if breadth:
        parts.append("global participation is " + {"positive": "positive", "negative": "weak"}.get(breadth["direction"], "mixed"))
    text = ""
    if parts:
        head = parts[0] + (", but " if (pos and neg and len(parts) > 1) else ", and " if len(parts) > 1 else "")
        text = head + (", ".join(parts[1:-1]) + (" and " if len(parts) > 2 else "") + parts[-1] if len(parts) > 1 else "") + "."
    if fii:
        text += f" The reported FII flow shows net {'buying' if fii['direction'] == 'positive' else 'selling'} in the previous session"
        text += (", and " + (vix_phrase(vix)) + ".") if vix else "."
    elif vix:
        text += " " + vix_phrase(vix).capitalize() + "."
    text += " There is no clear alignment across the available signals." if (pos and neg) else " The available signals point the same way." if (pos or neg) else ""
    return {"title": title, "text": text.strip()}


def vix_phrase(vix: dict) -> str:
    interp = (vix.get("interpretation") or "").lower()
    return "India VIX remains elevated" if "elevated" in interp else "India VIX is low" if "low" in interp else "India VIX is moderate"


def build_scenarios(rows: list[dict], catalysts: list[dict], *, target_label: str, generated_at: str, gift_status: str | None,
                    result_direction: str | None = None) -> dict:
    """Three conditional paths written from the current overnight observations (value, source and time shown with each). They state what to
    watch and what would confirm it. No probability, target, range, support or resistance, and none is marked as the expected one."""
    directional = [r for r in rows if r.get("direction") in ("positive", "negative", "neutral")]
    if not directional:
        return {"available": False, "reason": "Overnight signals are unavailable right now.", "target": target_label, "generated_at": generated_at}
    gift = _row(rows, "GIFT")
    gm = _gift_move(gift)
    gnow = f" (now {gift['value']})" if gift and gift.get("value") else ""
    up_t, mid_t, down_t = _TITLES.get(result_direction or "", _DEFAULT_TITLES)
    holding = ("remains positive" if gift and gift["direction"] == "positive" else "turns positive") if gift else "improve"
    after_fall = result_direction != "Positive"
    scenarios = [
        {"key": "bullish", "title": up_t,
         "condition": (f"If GIFT Nifty{gnow} {holding} and global participation improves, watch whether Indian market breadth strengthens after the open."
                       if gift else "If the overnight signals improve, watch whether Indian market breadth strengthens after the open."),
         "confirmation": "stronger breadth and a sustained index recovery." if after_fall else "broad participation and follow-through in the index.",
         "watch": [f"{r['label']} turning positive" for r in directional if r["direction"] != "positive"][:3] or ["Overnight signals staying positive"]},
        {"key": "neutral", "title": mid_t,
         "condition": "If GIFT Nifty stays near flat while global markets and US futures disagree, watch whether the index holds a narrow range without broad participation.",
         "confirmation": "mixed breadth and limited follow-through.",
         "watch": [f"{r['label']} staying {r['direction']}" for r in directional[:3]]},
        {"key": "bearish", "title": down_t,
         "condition": (f"If GIFT Nifty{gnow} turns negative and global markets weaken further, watch whether the previous session's selling extends into the next session."
                       if after_fall else f"If GIFT Nifty{gnow} turns negative and global markets weaken further, watch whether the previous session's gains are reversed."),
         "confirmation": "weakening breadth and persistent pressure on major indices.",
         "watch": [f"{r['label']} turning negative" for r in directional if r["direction"] != "negative"][:3] or ["Overnight signals staying negative"]},
    ]
    current = [{"label": r["label"], "reading": r.get("value"), "direction": r["direction"], "detail": r.get("detail"),
                "interpretation": r.get("interpretation"), "source": r.get("source"), "observed_at": r.get("observed_at"), "time_basis": r.get("time_basis")}
               for r in rows]
    return {"available": True, "target": target_label, "generated_at": generated_at, "current_signals": current, "setup": _setup(rows),
            "scenarios": scenarios, "catalysts": [f"{c.get('title')} ({c.get('date')})" for c in catalysts[:3] if c.get("title")],
            "gift_nifty_status": gift_status,
            "note": "Conditional paths, not predictions. No probability, target, range or support/resistance is given, and none is marked as expected."}


# ── investor takeaway ───────────────────────────────────────────────────────────────────────────────────────────────

def build_takeaway(drivers: dict, scenarios: dict, verdict: dict, breadth_tone: str | None, catalysts: list[dict]) -> dict:
    """The most important development, the key uncertainty and what to observe. Built from different inputs than the 30-second
    summary (which names the session outcome and the strongest signals) so the two do not repeat each other."""
    items = [i for i in drivers.get("items", []) if i["evidence_label"] != COMMENTARY]
    top = next((i for i in items if i["evidence_label"] == CONFIRMED), items[0] if items else None)
    development = None
    if top:
        how = ("The source ties it to the session's move and the verified data agrees." if top["evidence_label"] == CONFIRMED
               else "It coincided with the session; the data does not show that it caused the move.")
        development = {"headline": top["headline"], "evidence_label": top["evidence_label"], "text": how, "id": top["id"]}

    if not any(i["evidence_label"] == CONFIRMED for i in items):
        uncertainty = "No development is confirmed as the cause of the move, so the developments listed are potential contributors only." if items else \
            "No development met the evidence threshold, so the cause of the session's move is not established."
    elif breadth_tone == "broad_decline" and verdict.get("direction") == "Positive":
        uncertainty = "The index gain was narrow, so it is unclear how much of the market took part."
    elif scenarios.get("available") and any(r["direction"] == "positive" for r in scenarios["current_signals"]) and any(r["direction"] == "negative" for r in scenarios["current_signals"]):
        n_pos = sum(r["direction"] == "positive" for r in scenarios["current_signals"])
        n_neg = sum(r["direction"] == "negative" for r in scenarios["current_signals"])
        uncertainty = f"Overnight signals disagree ({n_pos} positive, {n_neg} negative), so the next open has no clear lean."
    elif scenarios.get("gift_nifty_status") == "stale":
        uncertainty = "The GIFT Nifty reading is stale, so the overnight read is weaker than usual."
    else:
        uncertainty = "Whether the move persists depends on what the overnight and scheduled data show."

    monitor: list[str] = []
    if top and top["sectors"]:
        monitor.append(f"Whether the {top['sectors'][0]['name']} move holds in the next session")
    if scenarios.get("available"):
        monitor += [w for w in scenarios["scenarios"][0]["watch"][:1]] + [w for w in scenarios["scenarios"][2]["watch"][:1]]
    monitor += [f"{c.get('title')} ({c.get('date')})" for c in catalysts[:2] if c.get("title")]
    seen, out = set(), []
    for m in monitor:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return {"development": development, "uncertainty": uncertainty, "monitor": out[:4]}


def window_start_utc(reference_session_date, now: datetime) -> tuple[datetime, int]:
    """Events from the close of the session before the reference session until now (overnight news counts), capped at 120 hours.
    Returns (start, hours_back)."""
    from app.services.market_session_state import IST, previous_trading_day
    prev = previous_trading_day(reference_session_date)
    start = datetime(prev.year, prev.month, prev.day, 15, 30, tzinfo=IST).astimezone(timezone.utc)
    hours = int(min(120, max(24, (now - start).total_seconds() / 3600 + 1)))
    return start, hours

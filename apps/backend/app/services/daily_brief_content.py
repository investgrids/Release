"""Phase 2 content helpers for the Daily Brief: evidence-backed catalysts/risks, sentence ledger for de-duplication, and
session-aware FAQ construction. Pure functions: no network, no DB, no LLM."""
from __future__ import annotations

import re

from app.services.daily_brief_composer import NEAR_FLAT_PCT


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def sentences_of(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text or "") if p.strip()]


class Ledger:
    """Remembers what each surface already says so a later surface does not repeat it."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def add(self, text: str) -> None:
        for s in sentences_of(text):
            self._seen.add(normalise(s))

    def fresh_sentences(self, text: str) -> list[str]:
        return [s for s in sentences_of(text) if normalise(s) not in self._seen]

    def is_duplicate(self, text: str) -> bool:
        parts = sentences_of(text)
        return bool(parts) and all(normalise(s) in self._seen for s in parts)


# ── catalysts / risks ───────────────────────────────────────────────────────────────────────────────────────────────

# Rising is BAD for Indian equities for these (import cost, rupee weakness, volatility); rising is good for none of them.
_RISE_IS_RISK = {"BRENT_CRUDE", "USD_INR", "INDIA_VIX"}
_OUTCOME_INDICES = {"NIFTY_50", "BANK_NIFTY", "SENSEX"}   # outcomes of the session, not drivers of it


def _graph_clause(graph, variable: str) -> str:
    """': typically pressures A, B and typically helps C (knowledge graph).' from the graph's own edges, or '.' when it has none."""
    row = graph.exposure(variable) if graph is not None else None
    if not row:
        return "."
    parts = []
    if row["pressured"]:
        parts.append("typically pressures " + ", ".join(x["sector"] for x in row["pressured"][:3]))
    if row["helped"]:
        parts.append("typically helps " + ", ".join(x["sector"] for x in row["helped"][:3]))
    return (": " + " and ".join(parts) + " (knowledge graph).") if parts else "."


def _explain_signal(f: dict, rising: bool, graph=None) -> tuple[str, str]:
    """(kind, explanation) for a market signal fact. Numbers come from the fact; any sector exposure comes from the knowledge graph."""
    key, name, value = f.get("entity_key"), f.get("name"), f.get("value")
    pct = f.get("change_pct")
    if pct is None:
        pct = f.get("numeric_value") if f.get("entity_type") == "market_index" else None
    move = f" ({pct:+.2f}%)" if isinstance(pct, (int, float)) else ""
    if key == "INDIA_VIX":
        return ("risk", f"India VIX {'rose' if rising else 'fell'} to {value}{move}: implied volatility is {'higher' if rising else 'lower'}.")
    if key == "BRENT_CRUDE":
        return ("risk" if rising else "catalyst",
                f"Brent crude is {'rising' if rising else 'falling'} at {value}" + _graph_clause(graph, "crude_rising" if rising else "crude_falling"))
    if key == "USD_INR":
        return ("risk" if rising else "catalyst",
                f"USD/INR is {'higher' if rising else 'lower'} at {value}" + _graph_clause(graph, "rupee_weaker" if rising else "rupee_stronger"))
    return ("risk" if not rising else "catalyst", f"{name} {'rose' if rising else 'fell'}{move}.")


def catalysts_and_risks(facts: list[dict], graph=None) -> dict:
    """Names (backward compatible) plus evidence-backed explanations. Returns
    {catalysts, risks, catalyst_details, risk_details}; every detail carries the fact it came from."""
    cats: list[dict] = []
    risks: list[dict] = []
    for f in facts:
        etype, key, name = f.get("entity_type"), f.get("entity_key"), f.get("name")
        if etype == "macro" or key in _OUTCOME_INDICES:
            continue
        if etype == "event":
            sentiment = (f.get("evidence") or {}).get("sentiment")
            if sentiment not in ("bullish", "bearish"):
                continue
            item = {"name": name, "explanation": (f.get("claim") or name or "").strip(),
                    "source": f.get("source"), "fact_key": f.get("fact_key")}
            (cats if sentiment == "bullish" else risks).append(item)
            continue
        direction = (f.get("direction") or "").lower()
        if direction not in ("up", "down", "rising", "falling"):
            continue
        pct = f.get("change_pct") if f.get("change_pct") is not None else (f.get("numeric_value") if etype == "market_index" else None)
        if isinstance(pct, (int, float)) and abs(pct) < NEAR_FLAT_PCT:
            continue
        rising = direction in ("up", "rising")
        kind, why = _explain_signal(f, rising, graph)
        if key in _RISE_IS_RISK:
            kind = "risk" if rising else "catalyst"
        item = {"name": name, "explanation": why, "source": f.get("source"), "fact_key": f.get("fact_key")}
        (risks if kind == "risk" else cats).append(item)
    cats, risks = cats[:4], risks[:4]
    return {"catalysts": [c["name"] for c in cats], "risks": [r["name"] for r in risks],
            "catalyst_details": cats, "risk_details": risks}


# ── summary, FAQs, evidence ────────────────────────────────────────────────────────────────────────────────────────

from app.services.daily_brief_composer import _fmt_date, clean_quote, _sector_moves  # noqa: E402
from app.services.market_session_state import AFTER_CLOSE, OPEN, MarketSession  # noqa: E402

_DIR_WORD = {"Positive": "positive", "Negative": "negative", "Neutral": "flat"}


def _first_sentence(text: str) -> str:
    parts = sentences_of(text)
    return parts[0] if parts else ""


def _ensure_stop(text: str) -> str:
    t = (text or "").strip()
    return t if not t or t[-1] in ".!?" else t + "."


def _when(session: MarketSession) -> str:
    if session.state in (AFTER_CLOSE, OPEN):
        return "today"
    return f"in the last session ({_fmt_date(session.reference_session_date)})"


def build_summary(session: MarketSession, verdict: dict, catalyst_details: list[dict], risk_details: list[dict],
                  events_top: list[dict], drivers: dict | None = None) -> str:
    """The 30-second answer. It does not restate the verdict card or the signal tiles next to it: it names the session outcome in a few
    words and says what the page below holds (counts only), so every sentence on the page is said once. Without driver data (older
    callers) it falls back to naming the strongest supportive signal and the main risk."""
    kind = verdict.get("kind")
    if kind == "forecast":
        if verdict.get("direction"):
            lead = f"Opening outlook for {_fmt_date(session.forecast_target_date)}: {_DIR_WORD.get(verdict['direction'], 'mixed')}."
        else:
            lead = f"No opening direction for {_fmt_date(session.forecast_target_date)}: the signals disagree."
    elif kind == "realized":
        lead = f"{verdict.get('headline')} on {_fmt_date(session.reference_session_date)}."
    else:
        lead = "Market data is limited right now."

    parts = [lead]
    if drivers is not None:
        n_dev, n_sig = len(drivers.get("items") or []), len(catalyst_details) + len(risk_details)
        pieces = []
        if n_dev:
            pieces.append(f"{n_dev} market development{'s' if n_dev != 1 else ''}")
        if n_sig:
            pieces.append(f"{n_sig} signal{'s' if n_sig != 1 else ''}")
        parts.append((" and ".join(pieces) + " are flagged below.") if pieces else "No development or signal met the evidence threshold.")
        return " ".join(parts)
    if catalyst_details:
        parts.append("Supportive signal: " + _ensure_stop(_first_sentence(catalyst_details[0]["explanation"])))
    elif events_top:
        e = events_top[0]
        parts.append("Top event: " + _ensure_stop(e.get("one_liner") or e.get("headline") or ""))
    if risk_details:
        parts.append("Main risk: " + _ensure_stop(_first_sentence(risk_details[0]["explanation"])))
    return " ".join(p for p in parts if p.strip())


def _pct_text(pct: float) -> str:
    return f"{pct:+.2f}%"


def build_questions(session: MarketSession, verdict: dict, snapshot: dict, events_top: list[dict], facts: list[dict],
                    watch_next: list[dict], risk_details: list[dict], ledger: "Ledger", drivers: dict | None = None) -> list[dict]:
    """Session-aware, question-specific FAQs. Every answer comes from a different slice of data than the verdict card and the
    30-second answer, and nothing is added whose sentences already appear elsewhere (ledger)."""
    when = _when(session)
    cands: list[dict] = []

    # 1. levels (realized) or the signal inputs (forecast)
    if verdict.get("kind") == "forecast":
        sigs = (verdict.get("forecast") or {}).get("signals") or []
        if sigs:
            cands.append({
                "question": f"What are the signals behind the opening outlook for {_fmt_date(session.forecast_target_date)}?",
                "answer": "; ".join(f"{s['label']}: {s['direction']}" + (f" ({s['detail']})" if s.get("detail") else "") for s in sigs[:5]) + ".",
                "links": [{"label": "Pre-market intelligence", "href": "/market-intelligence"}],
            })
    else:
        names = [("Nifty 50", "nifty"), ("Sensex", "sensex"), ("Bank Nifty", "banknifty"), ("India VIX", "vix")]
        bits = []
        for label, key in names:
            q = clean_quote(snapshot.get(key))
            if q:
                bits.append(f"{label} {q['value']} ({_pct_text(q['pct'])})")
        if bits:
            if session.state == AFTER_CLOSE:
                qtext = "What were the key index levels at the close?"
            elif session.state == OPEN:
                qtext = "What are the key index levels right now?"
            else:
                qtext = f"What were the key index levels in the last session ({_fmt_date(session.reference_session_date)})?"
            cands.append({"question": qtext, "answer": ", ".join(bits) + ".",
                          "links": [{"label": "Market Intelligence", "href": "/market-intelligence"}]})

    # 2. sectors
    moves = sorted(_sector_moves(snapshot.get("sectors")), key=lambda m: m[1])
    if len(moves) >= 2:
        best = [(n, p) for n, p in reversed(moves[-3:]) if p > 0]
        worst = [(n, p) for n, p in moves[:3] if p < 0]
        led = "Led: " + ", ".join(f"{n} {_pct_text(p)}" for n, p in best) + "." if best else "No tracked sector gained."
        lagged = "Lagged: " + ", ".join(f"{n} {_pct_text(p)}" for n, p in worst) + "." if worst else "No tracked sector fell."
        cands.append({
            "question": f"Which sectors led and lagged {when}?",
            "answer": f"{led} {lagged}",
            "links": [{"label": "Sector Intelligence", "href": "/sectors"}],
        })

    # 3. movers (price moves only, no attribution)
    mv = snapshot.get("movers") or {}
    gain = [g for g in (mv.get("gainers") or []) if g.get("name") or g.get("symbol")]
    lose = [g for g in (mv.get("losers") or []) if g.get("name") or g.get("symbol")]
    if gain or lose:
        def fmt(xs):
            return ", ".join(f"{x.get('symbol') or x.get('name')} {x.get('value')}" for x in xs)
        answer = " ".join(p for p in (f"Top gainers among tracked large caps: {fmt(gain)}." if gain else "",
                                      f"Top losers: {fmt(lose)}." if lose else "") if p)
        cands.append({"question": f"Which large-cap stocks moved the most {when}?", "answer": answer,
                      "links": [{"label": "Top movers", "href": "/market-intelligence"}]})

    # 4. what moved the market, by evidence label (never a causal claim for a same-day coincidence)
    groups = (drivers or {}).get("groups") or {}
    conf, pot = groups.get("confirmed_driver") or [], groups.get("potential_contributor") or []
    if conf or pot:
        parts = []
        if conf:
            parts.append("Confirmed: " + "; ".join(_ensure_stop(c["headline"]).rstrip(".") for c in conf[:2]) + ".")
        if pot:
            parts.append("Potential contributors: " + "; ".join(_ensure_stop(p["headline"]).rstrip(".") for p in pot[:2]) + ". Timing alone does not establish cause.")
        cands.append({"question": f"What may have moved the market {when}?", "answer": " ".join(parts),
                      "links": [{"label": "View all events", "href": "/events"}]})
    elif events_top:
        e = events_top[0]
        body = _ensure_stop(e.get("one_liner") or e.get("headline") or "")
        sect = f" Sectors tagged: {', '.join((e.get('sectors') or [])[:3])}." if e.get("sectors") else ""
        cands.append({"question": "What is the most important market-moving event right now?",
                      "answer": f"{body} MarketRipple rates it {e.get('priority_tier', 'High')} priority.{sect}",
                      "links": [{"label": "View all events", "href": "/events"}]})

    # 5. volatility: stated from the VIX fact itself, in different words from the signal tiles beside the summary
    vix = next((f for f in facts if f.get("entity_key") == "INDIA_VIX" and isinstance(f.get("change_pct"), (int, float)) and f.get("value") not in (None, "", "—")), None)
    if vix and abs(vix["change_pct"]) >= NEAR_FLAT_PCT:
        rose = vix["change_pct"] > 0
        cands.append({"question": f"Did market volatility rise or fall {when}?",
                      "answer": f"India VIX stands at {vix['value']}, {'up' if rose else 'down'} {abs(vix['change_pct']):.2f}% in the session, so expected swings {'widened' if rose else 'narrowed'}.",
                      "links": [{"label": "Market Intelligence", "href": "/market-intelligence"}]})

    # 6. crude
    crude = next((f for f in facts if f.get("entity_key") == "BRENT_CRUDE" and (f.get("direction") or "").lower() in ("rising", "falling", "up", "down")), None)
    if crude and crude.get("affected_sectors"):
        cands.append({"question": "How are crude oil prices affecting Indian stocks?",
                      "answer": f"{_ensure_stop(crude['claim'])} Sectors typically sensitive to crude: {', '.join(crude['affected_sectors'][:4])}.",
                      "links": [{"label": "Commodities", "href": "/commodities"}]})

    # 7. what next
    if watch_next:
        items = [f"{w.get('title')} ({w.get('date')})" for w in watch_next[:3] if w.get("title")]
        if items:
            cands.append({"question": "What should investors watch next?", "answer": "; ".join(items) + ".",
                          "links": [{"label": "Economic calendar", "href": "/calendar"}]})

    out, seen_q = [], set()
    for c in cands:
        nq = normalise(c["question"])
        if nq in seen_q or ledger.is_duplicate(c["answer"]):
            continue
        seen_q.add(nq)
        ledger.add(c["answer"])
        out.append(c)
        if len(out) >= 5:
            break
    return out


def dedupe_evidence(facts: list[dict], ledger: "Ledger") -> list[dict]:
    """Evidence rows: one per market fact, no repeated claim, none that merely repeats the verdict or the summary. Event facts are not
    listed here: each development already shows its own source and time under 'What moved the market'."""
    out, seen = [], set()
    for f in facts:
        if f.get("entity_type") == "event":
            continue
        claim = (f.get("claim") or "").strip()
        norm = normalise(claim)
        if not claim or norm in seen or ledger.is_duplicate(claim):
            continue
        seen.add(norm)
        out.append({"claim": claim, "source": f.get("source"), "timestamp": f.get("observed_at"),
                    "confidence": f.get("confidence"), "as_of_session": f.get("as_of_session")})
    return out


def why_today_matters(facts: list[dict]) -> list[dict]:
    """Event/fact -> consequence -> sectors. Companies are never listed as 'affected': a ticker only appears under
    companies_named, for events whose own text names it, because an impact on a specific company is not established here."""
    out = []
    for f in facts:
        sectors = list(f.get("affected_sectors") or [])
        named = [str(t).upper().split(".")[0] for t in (f.get("affected_companies") or []) if t] if f.get("entity_type") == "event" else []
        if not sectors and not named:
            continue
        out.append({
            "event": f["name"], "consequence": f["claim"], "affected": sectors[:5], "companies_named": list(dict.fromkeys(named))[:5],
            "affected_label": "Sectors tagged" if f.get("entity_type") == "event" else "Typically sensitive sectors",
        })
        if len(out) >= 5:
            break
    return out

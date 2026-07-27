"""
AI Search Benchmark Runner.

Executes a benchmark dataset (dataset.json / golden_questions.json) against
a real, running MarketRipple backend, capturing structured outputs and
computing objective pass/fail signals. Subjective columns (Reasoning
Quality, Evidence Quality, the UI/UX star ratings, etc.) stay for manual
scoring in evaluation_sheet.csv — this runner only fills what can be
checked automatically from the response itself, and merges in a completed
evaluation_sheet.csv (via --ux-sheet) for the UX portion of the KPI
dashboard when you have one.

Usage:
    python runner.py --dataset golden --limit 20
    python runner.py --dataset full --limit 100 --delay 6.5
    python runner.py --dataset golden --ux-sheet evaluation_sheet.csv
    python runner.py --consistency 5 --question "HAL vs BEL"
    python runner.py --compare results/run_A.json results/run_B.json

Respects the backend's real rate limit (10/minute on /api/ai/search) via
--delay (default 6.5s floor between request *starts*, ~9.2/min headroom) —
adaptive, not a flat sleep: real queries are frequently already slower than
the floor (verified live: a genuine successful response took 86.7s with no
retries, just an inherently slow free-tier model), so the runner only
sleeps whatever's left after the request's own latency, never double-pays.
Total wall-clock time for the full 2,400-question set therefore depends on
how many questions land on a slow model, not a fixed multiplier — could be
2-6+ hours. Use --limit and/or --dataset golden for fast iteration.

Regression checks against expected_answers.json load automatically
whenever a question's text matches an entry — no separate flag needed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).parent
RESULTS_DIR = OUT_DIR / "results"


# ─────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────
def load_dataset(name: str) -> list[dict]:
    path = OUT_DIR / ("golden_questions.json" if name == "golden" else "dataset.json")
    return json.loads(path.read_text(encoding="utf-8"))


def load_company_lookup() -> dict[str, str]:
    """symbol/name (lowercased) -> canonical symbol, for company-detection scoring."""
    from data import COMPANIES
    lookup: dict[str, str] = {}
    for sym, name, _sector in COMPANIES:
        lookup[sym.lower()] = sym
        lookup[name.lower()] = sym
    return lookup


def load_sector_lookup() -> dict[str, str]:
    from data import COMPANIES
    return {sym: sector for sym, _name, sector in COMPANIES}


def load_sector_names() -> list[str]:
    from data import SECTOR_NAMES
    return SECTOR_NAMES


def load_expected_answers() -> dict[str, dict]:
    """question text (normalized) -> expected-answer record."""
    path = OUT_DIR / "expected_answers.json"
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {_norm(r["question"]): r for r in records}


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


# ─────────────────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────────────────
# Reused across calls rather than one-per-request — a thread pool is how we
# enforce a real wall-clock deadline. urllib's own `timeout=` only bounds
# individual socket operations (connect, each send/recv), not the request as
# a whole: verified live that a request survived a ~2h41m gap where the
# entire backend process was suspended (Windows put the machine to sleep
# mid-request) and `urlopen` never raised — it just silently resumed and
# "succeeded" 9699s later, which would have quietly corrupted every latency
# stat in the benchmark. Wrapping the call in a future with `.result(timeout=)`
# means we stop *waiting* at the intended deadline regardless of what the
# underlying socket is doing; the abandoned thread is left to finish (or hang)
# on its own without blocking the benchmark loop.
_HTTP_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-search-call")


def _do_call(url: str, body: bytes, timeout: float) -> tuple[int, dict | None, str | None]:
    req = urllib.request.Request(url, data=body, method="POST",
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload.get("result"), None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail", str(e))
        except Exception:
            detail = str(e)
        return e.code, None, detail
    except Exception as e:  # noqa: BLE001 — surfacing any transport error as a result row
        return 0, None, str(e)


def call_ai_search(base_url: str, query: str, timeout: float, pipeline: str = "v2") -> tuple[int, dict | None, str | None, float]:
    """Returns (http_status, parsed_result_or_None, error_or_None, latency_seconds).
    Enforces a real wall-clock deadline (timeout + 10s grace for urllib's own
    socket-level timeout to fire first and produce a cleaner error) — see
    _HTTP_POOL's comment for why urllib's own timeout isn't sufficient alone.
    `pipeline="v3"` hits the new non-streaming benchmark-comparison endpoint
    (POST /api/ai/search/v3) instead of the untouched V2 endpoint — see the
    V3 Phase 1 plan's migration section on why this is a separate route
    rather than a flag-day cutover."""
    path = "/api/ai/search/v3" if pipeline == "v3" else "/api/ai/search"
    url = f"{base_url.rstrip('/')}{path}"
    body = json.dumps({"query": query}).encode("utf-8")
    t0 = time.monotonic()
    future = _HTTP_POOL.submit(_do_call, url, body, timeout)
    try:
        status, result, error = future.result(timeout=timeout + 10)
        return status, result, error, time.monotonic() - t0
    except concurrent.futures.TimeoutError:
        future.cancel()  # no-op if already running, but avoids leaking the Future's own state
        return 0, None, f"client-side wall-clock timeout after {timeout + 10:.0f}s (stopped waiting; server may still be processing)", time.monotonic() - t0


def detect_mentioned_companies(question: str, lookup: dict[str, str]) -> set[str]:
    ql = question.lower()
    hits = set()
    for key, sym in lookup.items():
        if len(key) >= 3 and re.search(r"\b" + re.escape(key) + r"\b", ql):
            hits.add(sym)
    return hits


def detect_mentioned_sectors(question: str, sector_names: list[str]) -> set[str]:
    """Word-boundary match against the same sector taxonomy the generator
    drew "Sector Analysis" questions from (data.SECTOR_NAMES) — e.g. "IT",
    "Banking", "Defence". Case-insensitive; short names like "IT" still need
    the word-boundary guard so "Fintech"/"cities" etc. don't false-positive."""
    ql = question.lower()
    hits = set()
    for name in sector_names:
        if re.search(r"\b" + re.escape(name.lower()) + r"\b", ql):
            hits.add(name)
    return hits


# ─────────────────────────────────────────────────────────────────────────
# Freshness scoring — "was live data used, how old, how many sources"
# ─────────────────────────────────────────────────────────────────────────
def score_freshness(result: dict) -> dict:
    now = datetime.now(timezone.utc)
    ages_min: list[float] = []
    for item in (result.get("news") or []) + (result.get("related_events") or []):
        ts = item.get("published_at") or item.get("date")
        if not ts or not isinstance(ts, str):
            continue
        # published_at is often relative ("38m ago") for the live feed and
        # ISO for DB rows — handle both rather than assuming one format.
        rel = re.match(r"(\d+)\s*([mhd])\s*ago", ts.strip().lower())
        if rel:
            n, unit = int(rel.group(1)), rel.group(2)
            ages_min.append(n * (1 if unit == "m" else 60 if unit == "h" else 1440))
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_min.append(max(0.0, (now - dt).total_seconds() / 60))
        except ValueError:
            continue

    source_count = len(result.get("news") or []) + len(result.get("related_events") or []) + len(result.get("policies") or [])
    return {
        "used_live_data": bool(ages_min),
        "newest_source_age_min": round(min(ages_min), 1) if ages_min else None,
        "source_count": source_count,
    }


# ─────────────────────────────────────────────────────────────────────────
# Regression scoring against expected_answers.json
# ─────────────────────────────────────────────────────────────────────────
def _narrative_text(result: dict) -> str:
    """Only the AI's actual explanatory prose — not the whole response dump,
    which also contains structured peer-company/sector lists where a
    must_not_mention name can legitimately appear as context (e.g. BEL
    listed as a defence-sector peer of HAL) without the AI ever claiming
    it. must_mention/must_not_mention should judge what the AI *said*, not
    what data happened to be attached alongside it."""
    answer = result.get("answer") or {}
    parts = [
        answer.get("summary", ""), answer.get("bottom_line", ""),
        answer.get("what_happened", ""), answer.get("why_it_happened", ""),
        answer.get("immediate_impact", ""), answer.get("medium_term", ""),
        answer.get("long_term", ""), answer.get("what_priced_in", ""),
    ]
    parts += [kd.get("explanation", "") for kd in (result.get("key_drivers") or [])]
    parts += [ins.get("summary", "") for ins in (result.get("insights") or [])]
    verdict = result.get("investment_verdict") or {}
    parts.append(verdict.get("verdict_basis", ""))
    return _norm(" ".join(p for p in parts if p))


_STOPWORDS = {"the", "and", "for", "with", "from", "into", "this", "that"}


def _phrase_covered(phrase: str, text: str) -> bool:
    """A multi-word theme like "volume growth" counts as covered either by
    the exact phrase, or by a majority of its own significant (4+ char,
    non-stopword) words appearing anywhere in the text — verified live that
    literal-phrase-only matching produces false negatives on real, on-topic
    answers: a genuine "Analyze Marico" response discussed "decline in sales
    volume" and "revenue growth" (right concepts) without ever using the
    literal string "volume growth". Still meaningfully selective — this
    isn't "does any word appear anywhere", it's "does this theme's own
    vocabulary show up", so an unrelated theme with no real overlap still
    correctly fails."""
    norm_phrase = _norm(phrase)
    if norm_phrase in text:
        return True
    words = [w for w in norm_phrase.split() if len(w) >= 4 and w not in _STOPWORDS]
    if not words:
        return False
    hits = sum(1 for w in words if w in text)
    return hits >= max(1, (len(words) + 1) // 2)


def score_against_expected(result: dict, expected: dict) -> dict:
    out = {
        "checked": True,
        "company_match": None, "sector_match": None, "confidence_ok": None,
        "must_mention_ok": None, "must_not_mention_ok": None,
        "hallucination_trap_handled": None, "expected_pass": True,
    }
    returned_syms = {c.get("symbol", "").upper() for c in (result.get("companies") or [])}
    full_text = _narrative_text(result)

    behavior = expected.get("expected_behavior", "normal")
    if behavior == "reject_unknown_entity":
        phrases = expected.get("must_mention", [])
        mode = expected.get("must_mention_match_mode", "any")
        hits = [p for p in phrases if _norm(p) in full_text]
        handled = (len(hits) > 0) if mode == "any" else (len(hits) == len(phrases))
        # A real fabricated company/price for the fake entity is the clear
        # failure signature even if it also happened to include a hedge phrase.
        fabricated = len(returned_syms) > 0
        out["hallucination_trap_handled"] = handled and not fabricated
        out["expected_pass"] = bool(out["hallucination_trap_handled"])
        return out

    expected_companies = set(expected.get("companies") or [])
    if expected_companies:
        out["company_match"] = expected_companies.issubset(returned_syms)

    from_lookup = load_sector_lookup()
    if expected_companies:
        expected_sectors = {from_lookup.get(s) for s in expected_companies if from_lookup.get(s)}
        returned_sectors = {from_lookup.get(s) for s in returned_syms if from_lookup.get(s)}
        if expected_sectors:
            out["sector_match"] = bool(expected_sectors & returned_sectors)

    # Confidence is tracked but never a pass/fail gate. Verified live: a
    # real "Analyze Marico" response scored confidence=15 — genuinely honest,
    # because the DB search found no fresh events/news specifically about
    # Marico right now (confidence_data.breakdown showed 0 sources, 0 market
    # confirmation). Gating on confidence_min would penalize the AI for
    # being honest about weak signal instead of fabricating false certainty
    # — the exact opposite of what this suite exists to catch. Same honesty
    # boundary as never asserting a fabricated investment "winner".
    conf_min = expected.get("confidence_min")
    if conf_min is not None:
        conf = (result.get("confidence_data") or {}).get("score")
        out["confidence_ok"] = conf is not None and conf >= conf_min

    must = expected.get("must_mention") or []
    if must:
        hits = [p for p in must if _phrase_covered(p, full_text)]
        out["must_mention_ok"] = len(hits) >= max(1, len(must) // 2)  # majority, not strict all

    must_not = expected.get("must_not_mention") or []
    if must_not:
        violations = [p for p in must_not if _norm(p) in full_text]
        out["must_not_mention_ok"] = len(violations) == 0

    # confidence_ok deliberately excluded — informational only, see above.
    checks = [v for v in (out["company_match"], out["must_mention_ok"], out["must_not_mention_ok"]) if v is not None]
    out["expected_pass"] = all(checks) if checks else True
    return out


# Categories whose questions are generated around a real, groundable event/
# news/policy trigger (as opposed to e.g. "Beginner Concepts" or "Risk
# Management", where there's nothing external to ground against) — used for
# "Event Detection" in the KPI dashboard: did the AI actually retrieve real
# supporting events/news/policies for a question that names one, rather than
# answering from generic knowledge alone.
EVENT_GROUNDED_CATEGORIES = {"Event Impact", "Earnings", "Government Policy", "Macro Economy"}


# ─────────────────────────────────────────────────────────────────────────
# Per-question scoring (single run)
# ─────────────────────────────────────────────────────────────────────────
def score_record(q: dict, status: int, result: dict | None, error: str | None,
                  latency: float, lookup: dict[str, str], expected_map: dict[str, dict],
                  sector_names: list[str] | None = None) -> dict:
    row = {
        "id": q["id"], "question": q["question"], "category": q["category"],
        "difficulty": q["difficulty"], "intent": q["intent"], "persona": q["persona"],
        "time_horizon": q["time_horizon"],
        "http_status": status, "response_time_s": round(latency, 2),
        "error": error or "",
        "response_type": "search",
        "answered": False, "synthesis_incomplete": None,
        "http_error": status != 200,
        "llm_failure": False,
        "main_answer_degraded": None,
        "confidence": None, "sources_count": None,
        "companies_detected_in_question": 0, "companies_returned_matched": 0,
        "company_detection_ok": None,
        "sectors_detected_in_question": 0, "sectors_returned_matched": 0,
        "sector_detection_ok": None,
        "event_detection_ok": None,
        "graph_link_valid": None,
        "decision_quality_ok": None,
        "historical_match_present": None,
        "hallucination_risk_flag": False,
        "verdict_rating": "", "verdict_direction": "",
        "timing": None,
        "freshness": None,
        "expected": None,
        "schema_version": "v2", "decision_quality_v2_ok": None,
        "evidence_score_present": None, "confidence_breakdown_present": None,
        "contradiction_flag": None, "validation_repairs_count": None, "specialist": "",
    }

    if status != 200 or result is None:
        return row

    # Market Pulse is a distinct, valid response family (top movers / sector
    # performance / market summary — e.g. "why is X rallying today") with a
    # completely different JSON shape from the standard search result: no
    # `answer.summary`, no `companies`, no `confidence_data`. Scoring it
    # against the standard-shape fields below would report a real, richly
    # answered query as "not answered" — verified live: a market_pulse
    # response for an Adani "rallying today" question came back with real
    # indices, real top gainers/losers, and a real narrative, but scored as
    # a false failure before this branch existed.
    if result.get("type") == "market_pulse":
        row["response_type"] = "market_pulse"
        row["answered"] = bool(result.get("ai_conclusion") or result.get("market_summary"))
        row["confidence"] = ((result.get("scores") or {}).get("market_confidence") or {}).get("score")
        row["sources_count"] = len(result.get("top_gainers", [])) + len(result.get("top_losers", []))
        mentioned = detect_mentioned_companies(q["question"], lookup)
        returned_syms = {m.get("ticker", "").upper() for m in
                         (result.get("top_gainers", []) + result.get("top_losers", []) + result.get("most_active", []))}
        row["companies_detected_in_question"] = len(mentioned)
        row["companies_returned_matched"] = len(mentioned & returned_syms)
        # A named company not among today's movers/most-active is expected,
        # not a detection failure — market pulse only ever returns a handful
        # of names, unlike the standard search's per-question company list.
        # Leave company_detection_ok as None (not applicable) for this type.
        return row

    row["answered"] = bool(result.get("answer", {}).get("summary"))
    row["synthesis_incomplete"] = bool(result.get("synthesis_incomplete"))
    # HTTP 200 but no real synthesis (either explicitly flagged degraded, or
    # the summary field came back empty) — distinct from a transport-level
    # http_error, this is the LLM/synthesis stage itself failing to produce
    # a usable answer even though the request succeeded.
    row["llm_failure"] = row["synthesis_incomplete"] or not row["answered"]
    # synthesis_incomplete is a COMBINED flag: it fires if the main answer
    # OR the separately-generated scenarios/checklist sub-call degrades (see
    # ai_search_service.py's own comment on _synthesis_incomplete). Verified
    # live: most synthesis_incomplete=True rows still have a fully real,
    # specific main answer — it was the scenarios sub-call that degraded, not
    # the core synthesis. The generic fallback template always starts with
    # this exact fixed string, so it's a reliable way to isolate "the actual
    # answer text is fabricated boilerplate" from "some secondary enrichment
    # call failed" — the former is a real quality problem, the latter mostly
    # reflects the number of extra LLM calls per query (a V3 design target).
    row["main_answer_degraded"] = (result.get("answer", {}).get("summary") or "").startswith(
        "Market intelligence analysis for:")
    conf_data = result.get("confidence_data") or {}
    row["confidence"] = conf_data.get("score", result.get("answer", {}).get("confidence"))
    row["sources_count"] = result.get("answer", {}).get("sources_count")
    row["historical_match_present"] = bool(result.get("historical_comparison"))
    verdict = result.get("investment_verdict") or {}
    row["verdict_rating"] = verdict.get("rating", "")
    row["verdict_direction"] = verdict.get("direction", "")
    # Decision quality: a real investment verdict needs a rating plus actual
    # reasoning behind it (basis or concrete top picks) — a rating alone
    # ("Buy") with nothing backing it isn't a usable decision aid. Only
    # judged when the response bothered to include a verdict block at all.
    if verdict:
        has_basis = bool(verdict.get("verdict_basis")) or bool(verdict.get("top_picks"))
        row["decision_quality_ok"] = bool(verdict.get("rating")) and has_basis
    row["timing"] = result.get("timing")
    row["freshness"] = score_freshness(result)

    # V3-only fields — schema_version absent means v2 (see runner's own
    # migration note: v3 is a strict superset of v2's field paths, so almost
    # nothing above needed to change; these are the genuinely new signals
    # v2 has no equivalent for).
    row["schema_version"] = result.get("schema_version", "v2")
    if row["schema_version"].startswith("v3"):
        dev2 = result.get("decision_engine_v2") or {}
        row["decision_quality_v2_ok"] = bool(dev2.get("verdict_scale")) and bool(dev2.get("why"))
        row["evidence_score_present"] = bool((result.get("evidence_score") or {}).get("stars"))
        row["confidence_breakdown_present"] = bool(result.get("confidence_breakdown"))
        validation = result.get("validation") or {}
        row["contradiction_flag"] = bool(validation.get("contradiction_flagged"))
        row["validation_repairs_count"] = len(validation.get("repairs") or [])
        row["specialist"] = result.get("specialist", "")
    else:
        row["decision_quality_v2_ok"] = None
        row["evidence_score_present"] = None
        row["confidence_breakdown_present"] = None
        row["contradiction_flag"] = None
        row["validation_repairs_count"] = None
        row["specialist"] = ""

    mentioned = detect_mentioned_companies(q["question"], lookup)
    returned_syms = {c.get("symbol", "").upper() for c in result.get("companies", [])}
    row["companies_detected_in_question"] = len(mentioned)
    row["companies_returned_matched"] = len(mentioned & returned_syms)
    if mentioned:
        row["company_detection_ok"] = bool(mentioned & returned_syms)

    if sector_names:
        mentioned_sectors = detect_mentioned_sectors(q["question"], sector_names)
        returned_sectors = {s.get("name") for s in (result.get("sectors") or []) if s.get("name")}
        row["sectors_detected_in_question"] = len(mentioned_sectors)
        row["sectors_returned_matched"] = len(mentioned_sectors & returned_sectors)
        if mentioned_sectors:
            row["sector_detection_ok"] = bool(mentioned_sectors & returned_sectors)

    # Event detection only applies to categories generated around a real
    # external trigger (an event/earnings/policy/macro topic) — grading it
    # on e.g. "Beginner Concepts" questions would penalize the AI for not
    # citing an event that was never part of the question.
    if q["category"] in EVENT_GROUNDED_CATEGORIES:
        row["event_detection_ok"] = bool(result.get("related_events") or result.get("news") or result.get("policies"))

    # Internal Link Accuracy: every graph edge must reference node ids that
    # actually exist in the same graph — a dangling edge is a real rendering
    # bug on the frontend (an edge pointing at nothing), not a scoring
    # artifact, so this is checked structurally rather than heuristically.
    graph = result.get("graph") or {}
    edges = graph.get("edges") or []
    if edges:
        node_ids = {n.get("id") for n in (graph.get("nodes") or [])}
        row["graph_link_valid"] = all(e.get("source") in node_ids and e.get("target") in node_ids for e in edges)

    high_conf_no_sources = (row["confidence"] is not None and row["confidence"] >= 85
                             and (row["sources_count"] or 0) == 0)
    named_company_missing = bool(mentioned) and not (mentioned & returned_syms)
    row["hallucination_risk_flag"] = high_conf_no_sources or named_company_missing

    expected = expected_map.get(_norm(q["question"]))
    if expected:
        row["expected"] = score_against_expected(result, expected["expected"])

    return row


# ─────────────────────────────────────────────────────────────────────────
# Main run
# ─────────────────────────────────────────────────────────────────────────
def run(dataset_name: str, limit: int | None, base_url: str, delay: float,
        timeout: float, out_name: str | None, ux_sheet: str | None, pipeline: str = "v2") -> Path:
    questions = load_dataset(dataset_name)
    if limit:
        questions = questions[:limit]
    lookup = load_company_lookup()
    expected_map = load_expected_answers()
    sector_names = load_sector_names()

    print(f"Running {len(questions)} questions from '{dataset_name}' against {base_url} (pipeline={pipeline})")
    print(f"Rate-limit delay: {delay}s/request (~{60/delay:.1f}/min)")
    print(f"Expected-answer checks loaded: {len(expected_map)}\n")

    results: list[dict] = []
    for i, q in enumerate(questions, 1):
        status, result, error, latency = call_ai_search(base_url, q["question"], timeout, pipeline=pipeline)
        row = score_record(q, status, result, error, latency, lookup, expected_map, sector_names)
        results.append(row)
        flag = "OK" if row["answered"] else ("RATE-LIMITED" if status == 429 else "FAIL")
        exp_flag = ""
        if row["expected"] is not None:
            exp_flag = " [EXPECTED-OK]" if row["expected"]["expected_pass"] else " [EXPECTED-FAIL]"
        print(f"[{i}/{len(questions)}] {flag:12s} {row['response_time_s']:6.2f}s  {q['question'][:60]}{exp_flag}")
        if i < len(questions):
            # Real queries are frequently already slower than the rate-limit
            # floor (verified live: a genuine, successful query took 86.7s
            # end-to-end with zero retries — just an inherently slow free-tier
            # model) — sleeping the full `delay` on top of that wastes real
            # time for no rate-limit benefit. Only sleep enough to keep the
            # gap between request *starts* at or above `delay`.
            remaining = delay - latency
            if remaining > 0:
                time.sleep(remaining)

    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = out_name or f"run_{dataset_name}_{ts}"
    json_path = RESULTS_DIR / f"{name}.json"
    csv_path = RESULTS_DIR / f"{name}.csv"

    ux_avg = merge_ux_scores(Path(ux_sheet)) if ux_sheet else None
    summary = build_summary(results, ux_avg)
    worst = top_worst_questions(results, 50)
    json_path.write_text(json.dumps({"summary": summary, "results": results, "top_worst_questions": worst},
                                     indent=2, ensure_ascii=False),
                          encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        flat = [_flatten(r) for r in results]
        # Union of keys across all rows, not just row 0 — rows without an
        # expected_answers match or without timing data simply omit those
        # keys, so a fixed header from a single row can undercount.
        fieldnames: list[str] = []
        seen = set()
        for row in flat:
            for k in row:
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat)

    write_html_dashboard(summary, results, RESULTS_DIR / f"{name}.html", worst)

    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {RESULTS_DIR / f'{name}.html'}")
    print_kpi_dashboard(summary)
    print_top_worst(worst)
    return json_path


def _flatten(row: dict) -> dict:
    flat = {k: v for k, v in row.items() if k not in ("timing", "freshness", "expected")}
    t = row.get("timing") or {}
    for k, v in t.items():
        flat[f"timing.{k}"] = v
    fr = row.get("freshness") or {}
    for k, v in fr.items():
        flat[f"freshness.{k}"] = v
    exp = row.get("expected")
    if exp:
        for k, v in exp.items():
            flat[f"expected.{k}"] = v
    return flat


def merge_ux_scores(path: Path) -> float | None:
    """Average the 7 UI/UX star columns (1-5) from a human-completed
    evaluation_sheet.csv, returned as a 0-10 scale to match the KPI
    dashboard's "Average UX Score X.X/10" format."""
    if not path.exists():
        print(f"  (--ux-sheet {path} not found, skipping UX score)")
        return None
    cols = [
        "AI Verdict Visible (1-5)", "Executive Summary Quality (1-5)",
        "Ripple Graph Quality (1-5)", "Comparison Quality (1-5)",
        "Sources Relevance (1-5)", "Recommendation Usefulness (1-5)",
        "Overall UX (1-5)",
    ]
    values: list[float] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for c in cols:
                v = (row.get(c) or "").strip()
                if v:
                    try:
                        values.append(float(v))
                    except ValueError:
                        pass
    if not values:
        print(f"  ({path} has no filled-in UX scores yet, skipping)")
        return None
    avg_5 = sum(values) / len(values)
    return round(avg_5 * 2, 1)  # 1-5 -> 0-10


# ─────────────────────────────────────────────────────────────────────────
# Summary / KPI dashboard
# ─────────────────────────────────────────────────────────────────────────
def build_summary(results: list[dict], ux_score_10: float | None = None,
                   consistency_pct: float | None = None) -> dict:
    n = len(results)
    answered = sum(1 for r in results if r["answered"])
    errored = sum(1 for r in results if r["http_status"] not in (200,))
    rate_limited = sum(1 for r in results if r["http_status"] == 429)
    confidences = [r["confidence"] for r in results if r["confidence"] is not None]
    latencies = [r["response_time_s"] for r in results]
    company_checks = [r for r in results if r["company_detection_ok"] is not None]
    company_ok = sum(1 for r in company_checks if r["company_detection_ok"])
    company_wrong_pct = round(100 * (1 - company_ok / len(company_checks)), 1) if company_checks else None
    hallucination_flags = sum(1 for r in results if r["hallucination_risk_flag"])
    hallucination_pct = round(100 * hallucination_flags / n, 1) if n else 0

    sector_checks = [r["expected"]["sector_match"] for r in results if r.get("expected") and r["expected"].get("sector_match") is not None]
    sector_wrong_pct = round(100 * (1 - sum(sector_checks) / len(sector_checks)), 1) if sector_checks else None

    expected_checked = [r for r in results if r.get("expected")]
    expected_passed = sum(1 for r in expected_checked if r["expected"]["expected_pass"])
    expected_pass_pct = round(100 * expected_passed / len(expected_checked), 1) if expected_checked else None

    fresh = [r["freshness"] for r in results if r.get("freshness")]
    live_data_pct = round(100 * sum(1 for f in fresh if f["used_live_data"]) / len(fresh), 1) if fresh else None
    avg_source_count = round(sum(f["source_count"] for f in fresh) / len(fresh), 1) if fresh else None
    source_relevance_pct = round(100 * sum(1 for f in fresh if f["source_count"] > 0) / len(fresh), 1) if fresh else None

    # Average speed breakdown across all runs that returned real timing data
    timings = [r["timing"] for r in results if r.get("timing")]
    avg_timing: dict[str, float] = {}
    if timings:
        keys = set().union(*(t.keys() for t in timings))
        for k in keys:
            vals = [t[k] for t in timings if k in t]
            avg_timing[k] = round(sum(vals) / len(vals), 1)

    by_category: dict[str, dict] = {}
    for r in results:
        c = by_category.setdefault(r["category"], {"total": 0, "answered": 0})
        c["total"] += 1
        c["answered"] += 1 if r["answered"] else 0

    pass_rate = round(100 * answered / n, 1) if n else 0

    # http_error = transport/status-level failure (never reached the LLM).
    # llm_failure = HTTP 200 but no usable synthesis (degraded/templated or
    # empty summary). Kept separate so a spike in one doesn't get buried in
    # the other — they point at different parts of the stack to fix.
    http_error_count = sum(1 for r in results if r.get("http_error"))
    http_error_pct = round(100 * http_error_count / n, 1) if n else 0
    llm_failure_count = sum(1 for r in results if r["http_status"] == 200 and r.get("llm_failure"))
    llm_failure_pct = round(100 * llm_failure_count / n, 1) if n else 0

    # Core Answer Quality: isolates "the actual answer text is real" from
    # "some secondary enrichment call (scenarios/checklist) also degraded" —
    # see main_answer_degraded's own comment in score_record. This is usually
    # a much higher number than the pass rate above, and the gap between them
    # is a direct measure of how much extra-LLM-call fragility is costing.
    main_degraded_checks = [r for r in results if r.get("main_answer_degraded") is not None]
    main_degraded_count = sum(1 for r in main_degraded_checks if r["main_answer_degraded"])
    core_answer_quality_pct = round(100 * (1 - main_degraded_count / len(main_degraded_checks)), 1) if main_degraded_checks else None

    # V3-only aggregates — None (not "0%") when the run is pure v2, so the
    # dashboard's fmt_n() correctly shows "n/a" rather than a misleading zero.
    v3_rows = [r for r in results if str(r.get("schema_version", "v2")).startswith("v3")]
    dqv2_checks = [r for r in v3_rows if r.get("decision_quality_v2_ok") is not None]
    decision_quality_v2_pct = round(100 * sum(1 for r in dqv2_checks if r["decision_quality_v2_ok"]) / len(dqv2_checks), 1) if dqv2_checks else None
    evidence_score_pct = round(100 * sum(1 for r in v3_rows if r.get("evidence_score_present")) / len(v3_rows), 1) if v3_rows else None
    contradiction_pct = round(100 * sum(1 for r in v3_rows if r.get("contradiction_flag")) / len(v3_rows), 1) if v3_rows else None
    specialist_counts: dict[str, int] = {}
    for r in v3_rows:
        sp = r.get("specialist") or "unknown"
        specialist_counts[sp] = specialist_counts.get(sp, 0) + 1

    sector_det_checks = [r for r in results if r.get("sector_detection_ok") is not None]
    sector_det_pct = round(100 * sum(1 for r in sector_det_checks if r["sector_detection_ok"]) / len(sector_det_checks), 1) if sector_det_checks else None

    event_det_checks = [r for r in results if r.get("event_detection_ok") is not None]
    event_det_pct = round(100 * sum(1 for r in event_det_checks if r["event_detection_ok"]) / len(event_det_checks), 1) if event_det_checks else None

    graph_checks = [r for r in results if r.get("graph_link_valid") is not None]
    graph_link_pct = round(100 * sum(1 for r in graph_checks if r["graph_link_valid"]) / len(graph_checks), 1) if graph_checks else None

    decision_checks = [r for r in results if r.get("decision_quality_ok") is not None]
    decision_quality_pct = round(100 * sum(1 for r in decision_checks if r["decision_quality_ok"]) / len(decision_checks), 1) if decision_checks else None

    # "Unknown Company Handling" = did the AI correctly refuse to fabricate
    # data for a company that doesn't exist, rather than hallucinating a
    # price/verdict for it (only measured on expected_answers.json's
    # reject_unknown_entity traps — there's no other ground truth for this).
    unknown_checks = [r["expected"]["hallucination_trap_handled"] for r in results
                       if r.get("expected") and r["expected"].get("hallucination_trap_handled") is not None]
    unknown_company_pct = round(100 * sum(unknown_checks) / len(unknown_checks), 1) if unknown_checks else None

    # Comparison Accuracy: pass rate restricted to Comparison-intent
    # questions specifically, not the overall pass rate — a product could
    # answer everything else well and still be bad at head-to-head calls.
    comparison_rows = [r for r in results if r["intent"] == "Comparison"]
    comparison_accuracy_pct = round(100 * sum(1 for r in comparison_rows if r["answered"]) / len(comparison_rows), 1) if comparison_rows else None

    # Historical Match Accuracy: scoped to the "Historical Events" category,
    # where a historical comparison is the whole point of the question —
    # reporting this over all categories would understate it (most
    # questions never ask for one) and overstate it if averaged loosely.
    historical_rows = [r for r in results if r["category"] == "Historical Events"]
    historical_match_pct = round(100 * sum(1 for r in historical_rows if r["historical_match_present"]) / len(historical_rows), 1) if historical_rows else None

    median_latency = round(statistics.median(latencies), 2) if latencies else 0

    # Top Failure Categories: ranked by failure rate (not raw count) so a
    # small, consistently-bad category isn't hidden behind a large category
    # with a few scattered misses — min 5 samples so single-digit categories
    # (e.g. a thin slice of "golden" run) don't dominate on noise.
    failure_rates = [
        (cat, round(100 * (c["total"] - c["answered"]) / c["total"], 1), c["total"] - c["answered"], c["total"])
        for cat, c in by_category.items() if c["total"] >= 5
    ]
    top_failure_categories = [
        {"category": cat, "failure_rate_pct": rate, "failed": failed, "total": total}
        for cat, rate, failed, total in sorted(failure_rates, key=lambda x: x[1], reverse=True)[:5]
        if rate > 0
    ]

    # Composite letter grade — weighted toward what actually matters for a
    # financial AI product: correctness and honesty over raw speed.
    grade_input = [
        (pass_rate, 0.35),
        (100 - hallucination_pct, 0.25),
        (consistency_pct if consistency_pct is not None else 100, 0.15),
        (source_relevance_pct if source_relevance_pct is not None else 100, 0.15),
        (100 if (sum(latencies) / n if n else 0) < 5 else 70, 0.10),
    ]
    composite = sum(v * w for v, w in grade_input)
    grade = "A" if composite >= 90 else "B" if composite >= 80 else "C" if composite >= 70 else "D" if composite >= 60 else "F"

    return {
        "total": n,
        "answered": answered,
        "pass_rate_pct": pass_rate,
        "errored": errored,
        "rate_limited": rate_limited,
        "http_error_count": http_error_count,
        "http_error_pct": http_error_pct,
        "llm_failure_count": llm_failure_count,
        "llm_failure_pct": llm_failure_pct,
        "core_answer_quality_pct": core_answer_quality_pct,
        "core_answer_quality_samples": len(main_degraded_checks),
        "pipeline_v3_samples": len(v3_rows),
        "decision_quality_v2_pct": decision_quality_v2_pct,
        "evidence_score_coverage_pct": evidence_score_pct,
        "contradiction_rate_pct": contradiction_pct,
        "specialist_counts": specialist_counts,
        "avg_response_time_s": round(sum(latencies) / n, 2) if n else 0,
        "median_response_time_s": median_latency,
        "p95_response_time_s": round(sorted(latencies)[int(0.95 * (n - 1))], 2) if n else 0,
        "avg_confidence": round(sum(confidences) / len(confidences), 1) if confidences else None,
        "confidence_samples": len(confidences),
        "company_detection_accuracy_pct": round(100 * company_ok / len(company_checks), 1) if company_checks else None,
        "wrong_company_detection_pct": company_wrong_pct,
        "wrong_sector_detection_pct": sector_wrong_pct,
        "company_detection_samples": len(company_checks),
        "sector_detection_accuracy_pct": sector_det_pct,
        "sector_detection_samples": len(sector_det_checks),
        "event_detection_accuracy_pct": event_det_pct,
        "event_detection_samples": len(event_det_checks),
        "graph_link_accuracy_pct": graph_link_pct,
        "graph_link_samples": len(graph_checks),
        "decision_quality_pct": decision_quality_pct,
        "decision_quality_samples": len(decision_checks),
        "unknown_company_handling_pct": unknown_company_pct,
        "unknown_company_samples": len(unknown_checks),
        "comparison_accuracy_pct": comparison_accuracy_pct,
        "comparison_samples": len(comparison_rows),
        "historical_match_accuracy_pct": historical_match_pct,
        "historical_match_samples": len(historical_rows),
        "hallucination_risk_flags": hallucination_flags,
        "hallucination_pct": hallucination_pct,
        "expected_answers_checked": len(expected_checked),
        "expected_answers_pass_pct": expected_pass_pct,
        "live_data_pct": live_data_pct,
        "avg_source_count": avg_source_count,
        "source_relevance_pct": source_relevance_pct,
        "avg_timing_ms": avg_timing,
        "ux_score_10": ux_score_10,
        "consistency_pct": consistency_pct,
        "overall_grade": grade,
        "composite_score": round(composite, 1),
        "by_category": by_category,
        "top_failure_categories": top_failure_categories,
    }


def print_kpi_dashboard(summary: dict) -> None:
    def fmt(v, suffix=""):
        return f"{v}{suffix}" if v is not None else "— (n/a)"

    def fmt_n(v, suffix="", n=None):
        base = fmt(v, suffix)
        return f"{base} (n={n})" if v is not None and n else base

    print("\n" + "=" * 68)
    print("  MarketRipple AI Search — Benchmark KPI Dashboard")
    print("=" * 68)
    print(f"  Questions                 {summary['total']}")
    print(f"  Pass Rate                 {summary['pass_rate_pct']}%  ({summary['answered']}/{summary['total']})")
    print(f"  Average Latency           {summary['avg_response_time_s']}s")
    print(f"  Median Latency            {summary['median_response_time_s']}s")
    print(f"  95th Percentile Latency   {summary['p95_response_time_s']}s")
    print(f"  LLM Failures              {summary['llm_failure_pct']}%  ({summary['llm_failure_count']}/{summary['total']})")
    print(f"  Core Answer Quality       {fmt_n(summary.get('core_answer_quality_pct'), '%', summary.get('core_answer_quality_samples'))}  (main answer real, ignoring secondary-call degradation)")
    print(f"  HTTP Errors               {summary['http_error_pct']}%  ({summary['http_error_count']}/{summary['total']})")
    print(f"  Hallucination Risk        {summary['hallucination_pct']}%  ({summary['hallucination_risk_flags']}/{summary['total']})")
    print(f"  Unknown Company Handling  {fmt_n(summary['unknown_company_handling_pct'], '%', summary['unknown_company_samples'])}")
    print(f"  Comparison Accuracy       {fmt_n(summary['comparison_accuracy_pct'], '%', summary['comparison_samples'])}")
    print(f"  Decision Quality          {fmt_n(summary['decision_quality_pct'], '%', summary['decision_quality_samples'])}")
    print(f"  Historical Match Accuracy {fmt_n(summary['historical_match_accuracy_pct'], '%', summary['historical_match_samples'])}")
    print(f"  Sector Detection          {fmt_n(summary['sector_detection_accuracy_pct'], '%', summary['sector_detection_samples'])}")
    print(f"  Company Detection         {fmt_n(summary['company_detection_accuracy_pct'], '%', summary['company_detection_samples'])}")
    print(f"  Event Detection           {fmt_n(summary['event_detection_accuracy_pct'], '%', summary['event_detection_samples'])}")
    print(f"  Internal Link Accuracy    {fmt_n(summary['graph_link_accuracy_pct'], '%', summary['graph_link_samples'])}")
    print(f"  Average Confidence        {fmt_n(summary['avg_confidence'], '%', summary['confidence_samples'])}")
    print(f"  Average UX Score          {fmt(summary['ux_score_10'], '/10')}")
    print(f"  Consistency               {fmt(summary['consistency_pct'], '%')}")
    if summary["expected_answers_checked"]:
        print(f"  Expected-Answer Pass Rate {summary['expected_answers_pass_pct']}% "
              f"(n={summary['expected_answers_checked']})")
    if summary["avg_timing_ms"]:
        print("\n  Avg Speed Breakdown:")
        for k, v in sorted(summary["avg_timing_ms"].items()):
            print(f"    {k:24s} {v}ms")
    if summary.get("top_failure_categories"):
        print("\n  Top Failure Categories:")
        for c in summary["top_failure_categories"]:
            print(f"    {c['category']:24s} {c['failure_rate_pct']}%  ({c['failed']}/{c['total']} failed)")
    if summary.get("pipeline_v3_samples"):
        print(f"\n  V3 Pipeline (n={summary['pipeline_v3_samples']}):")
        print(f"    Decision Quality v2        {fmt(summary.get('decision_quality_v2_pct'), '%')}")
        print(f"    Evidence Score Coverage    {fmt(summary.get('evidence_score_coverage_pct'), '%')}")
        print(f"    Contradiction Rate         {fmt(summary.get('contradiction_rate_pct'), '%')}")
        if summary.get("specialist_counts"):
            dist = ", ".join(f"{k}={v}" for k, v in summary["specialist_counts"].items())
            print(f"    Specialist routing         {dist}")
    print(f"\n  Overall Grade             {summary['overall_grade']}  (composite {summary['composite_score']}/100)")
    print("=" * 68)
    if summary["ux_score_10"] is None:
        print("  Note: UX score needs a human-completed evaluation_sheet.csv —")
        print("        pass it with --ux-sheet to include it.")
    if summary["consistency_pct"] is None:
        print("  Note: Consistency needs a separate `--consistency N --question ...` run.")
    print()


# ─────────────────────────────────────────────────────────────────────────
# Top-N worst questions — human-readable diagnostic reasons
# ─────────────────────────────────────────────────────────────────────────
def _diagnose_reason(row: dict) -> tuple[int, str] | None:
    """Returns (severity, reason) for the single most important thing wrong
    with this row, or None if nothing worth flagging. Severity drives sort
    order in the Top-N list — most consequential failures (never answered)
    outrank secondary quality issues (thin decision reasoning) so the list
    surfaces the questions actually worth fixing first, not just whatever
    happened to also be slow."""
    if row.get("http_error"):
        detail = (row.get("error") or "")[:120]
        return 100, f"HTTP {row['http_status']} error: {detail}" if detail else f"HTTP {row['http_status']} error"

    exp = row.get("expected")
    if exp and exp.get("hallucination_trap_handled") is False:
        return 95, "Failed to reject a fabricated/unknown company — treated it as real"

    if row.get("main_answer_degraded"):
        return 90, "Main answer is generic boilerplate — synthesis genuinely failed"

    if row.get("llm_failure") and not row.get("answered"):
        return 90, "No answer returned (empty synthesis)"

    # main_answer_degraded is explicitly False here (real content) but the
    # combined llm_failure flag still fired — the secondary scenarios/
    # checklist call degraded, not the core answer. Real, but much lower
    # severity than an actually-fabricated main answer.
    if row.get("llm_failure"):
        return 10, "Secondary enrichment (scenarios/checklist) degraded — main answer was real"

    if row.get("hallucination_risk_flag"):
        if row.get("confidence") is not None and row["confidence"] >= 85 and not (row.get("sources_count") or 0):
            return 70, f"High confidence ({row['confidence']}%) with zero supporting sources"
        return 70, "Named company from the question is missing from the response"

    if exp and exp.get("expected_pass") is False:
        if exp.get("company_match") is False:
            return 60, "Missing an expected company in the response"
        if exp.get("must_not_mention_ok") is False:
            return 60, "Mentioned a company that should have been excluded"
        if exp.get("must_mention_ok") is False:
            return 60, "Missing expected key facts/themes in the answer"
        return 60, "Failed expected-answer regression check"

    if row.get("company_detection_ok") is False:
        return 40, "Named company in the question not detected in the response"

    if row.get("graph_link_valid") is False:
        return 30, "Malformed intelligence graph — an edge references a missing node"

    if row.get("sector_detection_ok") is False:
        return 25, "Named sector in the question not reflected in the response"

    if row.get("event_detection_ok") is False:
        return 20, "No supporting event/news/policy grounding for an event-driven question"

    if row.get("decision_quality_ok") is False:
        return 15, "Investment verdict present but missing rating or reasoning"

    if row.get("response_time_s", 0) > 120:
        return 5, f"Very slow response ({row['response_time_s']}s)"

    return None


def top_worst_questions(results: list[dict], n: int = 50) -> list[dict]:
    diagnosed = []
    for r in results:
        d = _diagnose_reason(r)
        if d is not None:
            severity, reason = d
            diagnosed.append({
                "id": r["id"], "question": r["question"], "category": r["category"],
                "severity": severity, "reason": reason,
            })
    diagnosed.sort(key=lambda d: d["severity"], reverse=True)
    return diagnosed[:n]


def print_top_worst(worst: list[dict]) -> None:
    if not worst:
        print("  No failing/flagged questions found — nothing to list.\n")
        return
    print(f"\n  Top {len(worst)} Worst Questions")
    print("  " + "-" * 66)
    for i, w in enumerate(worst, 1):
        print(f"  Worst Question #{i}  [{w['id']}, {w['category']}]")
        print(f"    Question: {w['question']}")
        print(f"    Reason:   {w['reason']}")
        print("  " + "-" * 66)
    print()


# ─────────────────────────────────────────────────────────────────────────
# Consistency testing
# ─────────────────────────────────────────────────────────────────────────
def run_consistency(question: str, n: int, base_url: str, delay: float, timeout: float,
                     bypass_cache: bool = True) -> dict:
    print(f"Consistency test: asking the same question {n} times")
    print(f"  \"{question}\"")
    if bypass_cache:
        print("  (appending invisible zero-width-space cache-busters — same question to the LLM,"
              " different cache key, so each run is a genuinely independent call, not a cache hit)")
    print()
    verdicts = []
    for i in range(1, n + 1):
        # The backend caches identical query text (md5 of the lowercased,
        # stripped string) for several minutes — repeating the *exact* same
        # string just replays run 1's cached answer and would report a
        # meaningless 100%. A zero-width space (invisible, and .strip() only
        # trims the ends so mid-string ones survive) changes the cache key
        # without changing what the LLM actually reads.
        asked = question + ("​" * i if bypass_cache else "")
        status, result, error, latency = call_ai_search(base_url, asked, timeout)
        if status == 200 and result:
            verdict = result.get("investment_verdict") or {}
            label = verdict.get("rating") or verdict.get("direction") or "unknown"
            companies = [c.get("symbol") for c in (result.get("companies") or [])[:2]]
            top_pick = (verdict.get("top_picks") or companies or ["—"])[0]
            verdicts.append(top_pick)
            print(f"  Run {i}: {top_pick}  (verdict={label}, {latency:.1f}s)")
        else:
            verdicts.append(None)
            print(f"  Run {i}: FAILED ({error})")
        if i < n:
            remaining = delay - latency
            if remaining > 0:
                time.sleep(remaining)

    valid = [v for v in verdicts if v]
    most_common = statistics.mode(valid) if valid else None
    agree = sum(1 for v in valid if v == most_common) if most_common else 0
    consistency_pct = round(100 * agree / n, 1) if n else 0

    print(f"\n  Results: {verdicts}")
    print(f"  Consistency: {consistency_pct}% agreed on \"{most_common}\"")
    if consistency_pct < 100:
        print("  WARNING: answer flipped across identical runs — investigate before shipping.")

    return {"question": question, "runs": verdicts, "consistency_pct": consistency_pct, "majority": most_common}


# ─────────────────────────────────────────────────────────────────────────
# HTML dashboard
# ─────────────────────────────────────────────────────────────────────────
def write_html_dashboard(summary: dict, results: list[dict], path: Path,
                          worst: list[dict] | None = None) -> None:
    rows_html = "\n".join(
        f"<tr class=\"{'ok' if r['answered'] else 'fail'}\">"
        f"<td>{r['id']}</td><td>{r['category']}</td>"
        f"<td class='q'>{_esc(r['question'])}</td>"
        f"<td>{'✓' if r['answered'] else '✗'}</td>"
        f"<td>{r['response_time_s']}s</td>"
        f"<td>{r['confidence'] if r['confidence'] is not None else '—'}</td>"
        f"<td>{'⚠' if r['hallucination_risk_flag'] else ''}</td>"
        f"<td>{'✓' if r.get('expected') and r['expected']['expected_pass'] else ('✗' if r.get('expected') else '')}</td>"
        f"</tr>"
        for r in results
    )
    cat_rows = "\n".join(
        f"<tr><td>{cat}</td><td>{c['answered']}/{c['total']}</td>"
        f"<td>{round(100 * c['answered'] / c['total'], 1)}%</td></tr>"
        for cat, c in sorted(summary["by_category"].items())
    )
    timing_rows = "\n".join(
        f"<tr><td>{k}</td><td>{v}ms</td></tr>" for k, v in sorted(summary.get("avg_timing_ms", {}).items())
    )
    failure_cat_rows = "\n".join(
        f"<tr><td>{c['category']}</td><td>{c['failure_rate_pct']}%</td><td>{c['failed']}/{c['total']}</td></tr>"
        for c in summary.get("top_failure_categories", [])
    ) or "<tr><td colspan='3'>None — no category crossed the failure-rate threshold.</td></tr>"
    worst_html = "\n".join(
        f"<div class='worst'><b>#{i} [{w['id']}, {w['category']}]</b>"
        f"<div class='wq'>{_esc(w['question'])}</div>"
        f"<div class='wr'>{_esc(w['reason'])}</div></div>"
        for i, w in enumerate(worst or [], 1)
    ) or "<p>No failing/flagged questions found.</p>"

    def fmt(v, suffix=""):
        return f"{v}{suffix}" if v is not None else "—"

    html = f"""<!doctype html><meta charset="utf-8"><title>AI Search Benchmark Report</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0b0f1a;color:#dbe2ef;margin:0;padding:24px}}
h1{{font-size:20px}} h2{{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:#8ea0c8;margin-top:32px}}
.grade{{font-size:48px;font-weight:800}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}}
.stat{{background:#131a2b;border:1px solid #24304a;border-radius:10px;padding:12px}}
.stat b{{display:block;font-size:22px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:6px 8px;border-bottom:1px solid #1e2740;text-align:left}}
th{{color:#8ea0c8;position:sticky;top:0;background:#0b0f1a}}
tr.fail{{background:rgba(244,63,94,.08)}}
.q{{max-width:480px}}
.worst{{background:#131a2b;border:1px solid #24304a;border-left:3px solid #f43f5e;border-radius:8px;padding:10px 12px;margin:8px 0}}
.worst b{{color:#8ea0c8;font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
.wq{{margin-top:4px;font-size:14px}}
.wr{{margin-top:4px;font-size:12px;color:#fca5a5}}
</style>
<h1>AI Search Benchmark Report <span class="grade">{summary['overall_grade']}</span></h1>
<div class="stats">
  <div class="stat"><b>{summary['pass_rate_pct']}%</b>Pass rate ({summary['answered']}/{summary['total']})</div>
  <div class="stat"><b>{summary['avg_response_time_s']}s</b>Avg latency</div>
  <div class="stat"><b>{summary.get('median_response_time_s', '—')}s</b>Median latency</div>
  <div class="stat"><b>{summary['p95_response_time_s']}s</b>95th pct latency</div>
  <div class="stat"><b>{fmt(summary.get('llm_failure_pct'), '%')}</b>LLM failures (full response)</div>
  <div class="stat"><b>{fmt(summary.get('core_answer_quality_pct'), '%')}</b>Core answer quality</div>
  <div class="stat"><b>{fmt(summary.get('http_error_pct'), '%')}</b>HTTP errors</div>
  <div class="stat"><b>{summary['hallucination_pct']}%</b>Hallucination risk</div>
  <div class="stat"><b>{fmt(summary.get('unknown_company_handling_pct'), '%')}</b>Unknown company handling</div>
  <div class="stat"><b>{fmt(summary.get('comparison_accuracy_pct'), '%')}</b>Comparison accuracy</div>
  <div class="stat"><b>{fmt(summary.get('decision_quality_pct'), '%')}</b>Decision quality</div>
  <div class="stat"><b>{fmt(summary.get('historical_match_accuracy_pct'), '%')}</b>Historical match accuracy</div>
  <div class="stat"><b>{fmt(summary.get('sector_detection_accuracy_pct'), '%')}</b>Sector detection</div>
  <div class="stat"><b>{fmt(summary['company_detection_accuracy_pct'], '%')}</b>Company detection</div>
  <div class="stat"><b>{fmt(summary.get('event_detection_accuracy_pct'), '%')}</b>Event detection</div>
  <div class="stat"><b>{fmt(summary.get('graph_link_accuracy_pct'), '%')}</b>Internal link accuracy</div>
  <div class="stat"><b>{fmt(summary['avg_confidence'], '%')}</b>Avg confidence</div>
  <div class="stat"><b>{fmt(summary['ux_score_10'], '/10')}</b>Avg UX score</div>
  <div class="stat"><b>{fmt(summary['consistency_pct'], '%')}</b>Consistency</div>
  <div class="stat"><b>{fmt(summary['expected_answers_pass_pct'], '%')}</b>Expected-answer pass rate</div>
</div>
<h2>Top failure categories</h2>
<table><tr><th>Category</th><th>Failure rate</th><th>Failed / Total</th></tr>{failure_cat_rows}</table>
<h2>Speed breakdown (avg)</h2>
<table><tr><th>Stage</th><th>Time</th></tr>{timing_rows}</table>
<h2>By category</h2>
<table><tr><th>Category</th><th>Answered</th><th>Rate</th></tr>{cat_rows}</table>
<h2>Top {len(worst or [])} worst questions</h2>
{worst_html}
<h2>All results</h2>
<table><tr><th>ID</th><th>Category</th><th>Question</th><th>Answered</th><th>Time</th><th>Confidence</th><th>Risk</th><th>Expected✓</th></tr>{rows_html}</table>
"""
    path.write_text(html, encoding="utf-8")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─────────────────────────────────────────────────────────────────────────
# Compare (regression between two runs)
# ─────────────────────────────────────────────────────────────────────────
def compare(old_path: Path, new_path: Path) -> None:
    old = json.loads(old_path.read_text(encoding="utf-8"))
    new = json.loads(new_path.read_text(encoding="utf-8"))
    old_by_id = {r["id"]: r for r in old["results"]}
    new_by_id = {r["id"]: r for r in new["results"]}

    regressions, fixes = [], []
    for qid, new_r in new_by_id.items():
        old_r = old_by_id.get(qid)
        if old_r is None:
            continue
        if old_r["answered"] and not new_r["answered"]:
            regressions.append((qid, new_r["question"]))
        elif not old_r["answered"] and new_r["answered"]:
            fixes.append((qid, new_r["question"]))

    print(f"Comparing {old_path.name} -> {new_path.name}")
    print(f"  Old pass rate: {old['summary']['pass_rate_pct']}%  (grade {old['summary'].get('overall_grade', '—')})")
    print(f"  New pass rate: {new['summary']['pass_rate_pct']}%  (grade {new['summary'].get('overall_grade', '—')})")
    print(f"  Regressions (was answered, now failing): {len(regressions)}")
    for qid, q in regressions[:20]:
        print(f"    - [{qid}] {q}")
    print(f"  Fixes (was failing, now answered): {len(fixes)}")
    for qid, q in fixes[:20]:
        print(f"    + [{qid}] {q}")


# ─────────────────────────────────────────────────────────────────────────
# Re-report an already-completed run (no new HTTP calls)
# ─────────────────────────────────────────────────────────────────────────
def report(json_path: Path) -> None:
    """Regenerate the KPI dashboard + Top-50-worst report from a completed
    run's JSON, without re-querying the backend. Rebuilds the summary from
    the stored per-question rows rather than trusting the stored summary
    verbatim, so re-running this after a scoring-logic change (new KPI
    fields, a fixed heuristic) reflects the new logic against the same raw
    responses — old runs simply show "n/a" for fields their rows predate."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    results = data["results"]
    old_summary = data.get("summary", {})
    summary = build_summary(results, old_summary.get("ux_score_10"), old_summary.get("consistency_pct"))
    worst = top_worst_questions(results, 50)

    print(f"Report for {json_path.name} ({len(results)} questions)\n")
    print_kpi_dashboard(summary)
    print_top_worst(worst)

    html_path = json_path.with_suffix(".html")
    write_html_dashboard(summary, results, html_path, worst)
    print(f"Rewrote {html_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["golden", "full"], default="golden")
    ap.add_argument("--limit", type=int, default=None, help="Cap the number of questions run")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--delay", type=float, default=6.5, help="Seconds between requests (rate-limit safety)")
    # 60s undercounted real latency — verified live: a genuine, successful
    # /api/ai/search response (no retries, no rate-limiting, single provider)
    # took 86.7s end-to-end. That's a real product finding worth surfacing
    # in the baseline itself (see README), not a reason to raise this
    # silently — but a benchmark timeout tighter than real legitimate
    # latency just misreports working answers as failures.
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--out", default=None, help="Output file basename (default: auto-timestamped)")
    ap.add_argument("--ux-sheet", default=None, help="Path to a human-completed evaluation_sheet.csv, to include Average UX Score in the KPI dashboard")
    ap.add_argument("--compare", nargs=2, metavar=("OLD_JSON", "NEW_JSON"),
                     help="Compare two previous run JSON reports instead of running a new benchmark")
    ap.add_argument("--consistency", type=int, default=None, metavar="N",
                     help="Ask --question this many times and report answer consistency, instead of a full run")
    ap.add_argument("--question", default=None, help="Question text for --consistency mode")
    ap.add_argument("--no-cache-bypass", action="store_true",
                     help="For --consistency: don't cache-bust (repeats will just replay the cached first answer — mainly useful for testing the runner itself)")
    ap.add_argument("--report", metavar="RUN_JSON",
                     help="Regenerate the KPI dashboard + Top-50-worst report from a completed run's JSON, without re-running any queries")
    ap.add_argument("--pipeline", choices=["v2", "v3"], default="v2",
                     help="v2 hits the untouched /api/ai/search (default); v3 hits the new /api/ai/search/v3 "
                          "intelligence-pipeline endpoint for Phase 1 benchmark comparison runs")
    args = ap.parse_args()

    if args.report:
        report(Path(args.report))
        return

    if args.compare:
        compare(Path(args.compare[0]), Path(args.compare[1]))
        return

    if args.consistency:
        if not args.question:
            ap.error("--consistency requires --question")
        run_consistency(args.question, args.consistency, args.base_url, args.delay, args.timeout,
                         bypass_cache=not args.no_cache_bypass)
        return

    run(args.dataset, args.limit, args.base_url, args.delay, args.timeout, args.out, args.ux_sheet, pipeline=args.pipeline)


if __name__ == "__main__":
    main()

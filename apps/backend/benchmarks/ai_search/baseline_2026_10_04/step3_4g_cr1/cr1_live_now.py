"""CR1 with the LIVE feed as it is right now (no snapshot), model-free: what the repaired pipeline retrieves, ranks, shows the model, and what Gate A relies on. Zero provider calls."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent

from sqlalchemy import text  # noqa: E402

from app.api.companies import _NSE_UNIVERSE as UNIVERSE  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import entities as EN  # noqa: E402
from app.services.ai_search import evidence as E  # noqa: E402
from app.services.ai_search import evidence_sufficiency as SUFF  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent as D  # noqa: E402
from app.services.ai_search.specialists import company as C  # noqa: E402

CALLS = []


async def _rec(*a, **k):
    CALLS.append(1)
    return ""


S._call_with_fallback = _rec
QUERY = "What is the outlook for Kotak Mahindra Bank?"


async def main():
    ents, it = EN.extract_entities(QUERY), D(QUERY)
    async with AsyncSessionLocal() as db:
        await db.execute(text("select 1"))
        b = await E.collect(QUERY, it, ents, db)
        b.prompt_kind = "company"
        prompt = C.build_prompt(QUERY, b, it, ents)
        res = SUFF.assess(QUERY, it, ents, b, UNIVERSE)
    out = {"provider_calls_made": len(CALLS), "retrieval_failures": b.retrieval_failures,
           "news": [{"headline": n["headline"], "published_at": n.get("published_at"), "source": n.get("source"), "summary_NOT_visible": (n.get("summary") or "")[:200]} for n in b.news],
           "announcements": [a["subject"] for a in b.announcements], "events": [e["title"] for e in b.events], "context_lines": b.context_lines,
           "prompt_evidence_markers": sorted(set(__import__("re").findall(r"\[([ENPAC]\d{1,3})\]", prompt))), "gate_a": {"status": res["status"], "context": res["context"]},
           "visible_announcement_and_context_text": prompt[prompt.index("[C1]"):prompt.index("[C1]") + 1800] if "[C1]" in prompt else None}
    (HERE / "cr1_live_now.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str)[:6000])


asyncio.run(main())

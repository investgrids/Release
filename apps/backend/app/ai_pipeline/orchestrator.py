"""
The stage sequencer — Intent Detection -> Parallel Retrieval -> Evidence
Fusion -> Driver Ranking -> Decision Intelligence -> Answer Template ->
AI Reasoning -> Answer Validation -> PipelineResult.

Importing this module (directly, or via anything that imports it) triggers
registration of every intent/retriever/template/model-tier by importing
each of their packages once for the side effect — the only place in the
codebase that needs to know all four registries exist together.
"""
from __future__ import annotations

import asyncio
import sys

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

# Side-effect imports: populate the four registries before anything below runs.
from app.ai_pipeline import intent as _intent_pkg  # noqa: F401
from app.ai_pipeline import models as _models_pkg  # noqa: F401
from app.ai_pipeline import retrieval as _retrieval_pkg  # noqa: F401
from app.ai_pipeline import templates as _templates_pkg  # noqa: F401

from app.ai_pipeline.contracts import PipelineResult
from app.ai_pipeline.decision.decision_intelligence_engine import build_decision
from app.ai_pipeline.fusion.evidence_fusion_engine import fuse
from app.ai_pipeline.intent.fast_classifier import fast_classify
from app.ai_pipeline.models import model_router
from app.ai_pipeline.ranking.driver_ranking_engine import rank
from app.ai_pipeline.registry import INTENT_REGISTRY, TEMPLATE_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext
from app.ai_pipeline.retrieval.engine import parallel_retrieve
from app.ai_pipeline.templates.base import build_prompt, render
from app.ai_pipeline.validation.answer_validator import validate

log = structlog.get_logger(__name__)


async def run_pipeline(query: str, db: AsyncSession, *, history: list[str] | None = None) -> PipelineResult:
    intent_key = fast_classify(query)
    spec = INTENT_REGISTRY.get(intent_key)
    if spec is None:
        raise RuntimeError(f"No IntentSpec registered for classified intent '{intent_key}'")

    ctx = RetrievalContext(query=query, db=db, intent=intent_key)
    raw_evidence, degraded = await parallel_retrieve(spec.retrievers, ctx)

    fused_evidence, conflicts = fuse(raw_evidence)
    drivers = rank(fused_evidence)
    decision = build_decision(
        fused_evidence, drivers, spec.decision_profile, conflicts, degraded, spec.retrievers,
    )

    template = TEMPLATE_REGISTRY.get(spec.template)
    if template is None:
        raise RuntimeError(f"No AnswerTemplate registered for '{spec.template}'")

    prompt = build_prompt(template, query, decision, fused_evidence)
    try:
        # "best_reasoning" tries NVIDIA NIM directly first (its own dedicated
        # quota, separate from the shared OpenRouter free pool the "medium"
        # tier draws from), falling back to the full existing chain if
        # NVIDIA is unset or fails — see ai_pipeline/models/tiers.py.
        raw_answer = await model_router.call("best_reasoning", prompt, template.system_prompt)
    except Exception as exc:
        log.warning("ai_pipeline.reasoning_call_failed", error=str(exc)[:200])
        raw_answer = ""

    answer = render(template, raw_answer, query, decision, fused_evidence)
    validated_answer, report = await validate(template, answer, query, decision, fused_evidence)

    return PipelineResult(
        intent=intent_key,
        query=query,
        evidence=fused_evidence,
        drivers=drivers,
        decision=decision,
        answer=validated_answer,
        validator=report,
    )


async def _cli_main(query: str) -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await run_pipeline(query, db)

    print(f"\n=== Intent: {result.intent} ===")
    print(f"\n--- Evidence ({len(result.evidence)}) ---")
    for e in result.evidence[:10]:
        print(f"  [{e.source}] {e.entity or '-'}: {e.claim[:90]} "
              f"(polarity={e.polarity}, mag={e.magnitude:.2f}, conf={e.confidence:.2f})")

    print(f"\n--- Drivers ({len(result.drivers)}) ---")
    for d in result.drivers:
        print(f"  {d.label}: {d.score} ({d.direction})")

    print("\n--- Decision ---")
    print(f"  verdict={result.decision.verdict}")
    print(f"  mood={result.decision.mood}  risk={result.decision.risk_level}  horizon={result.decision.horizon}")
    print(f"  confidence={result.decision.confidence.total_score} ({result.decision.confidence.level})")
    print(f"  missing_data={result.decision.missing_data}")

    print("\n--- Answer ---")
    for k, v in result.answer.items():
        print(f"  {k}: {str(v)[:200]}")

    print("\n--- Validator ---")
    print(f"  passed={result.validator.passed}  missing={result.validator.missing_sections}"
          f"  repair_attempted={result.validator.repair_attempted}")


if __name__ == "__main__":
    # Windows' console defaults to cp1252, which can't encode characters an
    # LLM is free to emit (em-dashes, curly quotes, non-breaking hyphens).
    # Reconfigure stdout to UTF-8 so the CLI harness never crashes on the
    # model's own output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    q = " ".join(sys.argv[1:]) or "Should I invest in defence stocks after the latest budget?"
    asyncio.run(_cli_main(q))

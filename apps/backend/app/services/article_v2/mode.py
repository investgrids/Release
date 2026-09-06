"""
Article V2 Phase P5 — Entry-point mode boundary (owner design,
2026-09-06). The single, real place `ARTICLE_PIPELINE_MODE` gets parsed
and answered — no other module should read `settings.article_pipeline_mode`
directly or re-derive its own notion of "is V2 active."

|  Mode        | V1                       | V2 executes | V2 persists publicly    |
|--------------|--------------------------|-------------|--------------------------|
| v1           | Normal                   | No          | No                       |
| shadow_v2    | Normal                   | Yes         | No                       |
| canary_v2    | Normal for non-canaries  | Yes         | Only eligible canaries*  |
| v2           | Event flow replaced      | Yes         | Yes, subject to all gates|

*Not implemented by P5 -- `v2_may_persist_publicly()` is locked `False`
for every mode until P7 (evidence-quality-gated canary eligibility) is
built and separately authorized. `v2`'s "Event flow replaced" behavior
is also NOT implemented by P5 -- the mode is a recognized, valid config
value so this enum is complete, but nothing in P5 wires that cutover.

Default is always `"v1"`. Unknown, malformed, or missing configuration
also resolves to `v1` -- fail-closed, never an accidental V2 activation.
"""
from __future__ import annotations

from enum import Enum

from app.core.config import settings


class ArticlePipelineMode(str, Enum):
    V1 = "v1"
    SHADOW_V2 = "shadow_v2"
    CANARY_V2 = "canary_v2"
    V2 = "v2"


def get_article_pipeline_mode() -> ArticlePipelineMode:
    """The one real entry point for reading the mode. Fail-closed: any
    value that isn't exactly one of the 4 recognized strings (missing,
    empty, misspelled, legacy) resolves to V1 -- never guessed into a
    stronger mode than the config can actually prove."""
    raw = (settings.article_pipeline_mode or "").strip().lower()
    try:
        return ArticlePipelineMode(raw)
    except ValueError:
        return ArticlePipelineMode.V1


def v2_should_execute(mode: ArticlePipelineMode) -> bool:
    """Whether the real C1-C8.5+P1+P2+P4 path should run at all for this
    mode -- true for every mode except V1."""
    return mode != ArticlePipelineMode.V1


def v2_may_persist_publicly(mode: ArticlePipelineMode) -> bool:
    """The ONE function that answers "may V2 write a public
    IntelligenceArticle row right now" -- structurally, not by convention.
    Locked `False` unconditionally until P7 builds and this function is
    deliberately changed to consult real, evidence-quality-based canary
    eligibility (never a random traffic percentage, per the owner's own
    instruction). A caller must never call `publish_v2_article` without
    checking this first; the P5 orchestrator itself goes further and
    simply never imports `publish_v2_article` on the shadow path at all,
    so persistence is structurally unreachable there even if this
    function's answer were ever wrong."""
    return False

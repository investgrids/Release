"""
AEV2 rollout mode — the single, real place AI_SEARCH_AEV2_MODE gets parsed
and answered. Mirrors app/services/article_v2/mode.py's exact pattern
(same codebase precedent for a fail-closed, string-config rollout gate) —
no other module should read settings.ai_search_aev2_mode directly or
re-derive its own notion of "is AEV2 active."

| Mode    | Assembled? | In the HTTP response?                          | Telemetry |
|---------|-----------|--------------------------------------------------|-----------|
| off     | No        | Field absent                                      | None      |
| shadow  | Yes       | Field absent — never serialized to the caller     | Yes       |
| canary  | Yes       | Present only if the request carries a valid       | Yes       |
|         |           | X-Admin-Key (the existing admin-key gate already  |           |
|         |           | used for /api/graph/full — no new auth mechanism) |           |
| public  | Yes       | Present on success; null on assembly failure      | Yes       |

Default is always "off". Unknown, malformed, or missing configuration
also resolves to "off" — fail-closed, never an accidental activation.
"""
from __future__ import annotations

from enum import Enum

from app.core.config import settings


class AEV2Mode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    CANARY = "canary"
    PUBLIC = "public"


# Readiness latch — a CODE-level completeness gate, deliberately NOT an
# environment variable. Review finding (2026-09-21): the enum already
# supports canary/public, but this foundation slice only populates
# direct_conclusion — a config typo or an early flip of
# AI_SEARCH_AEV2_MODE must never accidentally expose that incomplete
# shape to a real user. An env var can fail open on a typo; a hardcoded
# Python constant cannot — flipping this requires an actual code change
# and a new commit, not a config edit. Set this True only in the same
# commit that finishes Build 1 (companies_affected attribution, full
# response restructuring) and claim-level citation resolution — see the
# approved spec's Sequencing section for what "complete" means here.
AEV2_BUILD_COMPLETE = False


def get_aev2_mode() -> AEV2Mode:
    """The one real entry point for reading the mode. Fail-closed: any
    value that isn't exactly one of the 4 recognized strings (missing,
    empty, misspelled, legacy) resolves to OFF — never guessed into a
    stronger mode than the config can actually prove."""
    raw = (settings.ai_search_aev2_mode or "").strip().lower()
    try:
        return AEV2Mode(raw)
    except ValueError:
        return AEV2Mode.OFF


def should_assemble(mode: AEV2Mode) -> bool:
    """Whether AEV2 should be computed at all for this mode — true for
    every mode except OFF. Shadow computes purely for telemetry; it is
    should_return_to_client (below), not this, that keeps it off the wire."""
    return mode != AEV2Mode.OFF


def should_return_to_client(mode: AEV2Mode, *, has_valid_admin_key: bool) -> bool:
    """Whether the assembled result may be serialized into the actual
    HTTP response this specific request receives. SHADOW never returns it
    regardless of the admin key — shadow mode's whole point is measuring
    without exposing; it is therefore also unaffected by the readiness
    latch below (shadow safely observes the incomplete foundation shape,
    it never ships it). CANARY and PUBLIC additionally require
    AEV2_BUILD_COMPLETE — see that constant's own docstring for why this
    is a code latch, not a config value."""
    if not AEV2_BUILD_COMPLETE:
        return False
    if mode == AEV2Mode.PUBLIC:
        return True
    if mode == AEV2Mode.CANARY:
        return has_valid_admin_key
    return False


def should_emit_telemetry(mode: AEV2Mode) -> bool:
    """SHADOW/CANARY/PUBLIC all emit sanitized telemetry — OFF emits
    nothing (no assembly ever ran)."""
    return mode != AEV2Mode.OFF

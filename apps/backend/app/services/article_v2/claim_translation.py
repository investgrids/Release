"""
Article V2 Phase P2 — CD3 Claim Authorization Translator (owner design,
2026-09-04, locked after 4 corrections on 2026-09-06). Answers: "given
one of C6's own ComposedClaim objects, what is MarketRipple actually
allowed to publish?" This is NOT a naive FACT -> AUTHORIZED lookup --
every claim is routed through the real claim_authorization.py capability
model (CD3-D), the same central contract every other public surface on
this platform is required to go through. A V2 article that skipped this
translation and trusted composer.py's own "VERIFIED" validation_status
as if it were a public-authorization decision would be exactly the kind
of second, drifting authorization path CD3-D exists to prevent.

## The four locked corrections (owner review, 2026-09-04)

1. A verified source/document FACT claim (real evidence_ids or
   financial_fact_ids) is `ClaimProvenance.DOCUMENTED_FACT`, never
   `HISTORICAL_OUTCOME` -- the latter is reserved for a real measured
   outcome-OVER-TIME pattern, which nothing in the V2 pipeline currently
   produces. See claim_provenance.py's own DOCUMENTED_FACT docstring.
2. `ctx.integrity_status` is checked FIRST, unconditionally, before any
   claim-shape inspection -- not bolted on afterward. A degraded/
   fallback/invalid evidence envelope authorizes nothing, regardless of
   what an individual claim's own text/shape looks like.
3. `PRICE_SIGN` (OBSERVED_DIRECTION) requires real structured market-
   observation proof -- an actual instrument+timestamp+change_pct, never
   inferred from `claim.evidence_ids`/`claim.financial_fact_ids` being
   non-empty, and never from a claim's own `text` or a section name.
   "Never infer semantics from field name or JSON shape."
4. INTERPRETATION claims are always QUALIFIED, never AUTHORIZED, and
   never rejected outright either -- ANALYTICAL_HYPOTHESIS/QUALIFIED,
   matching authorize_direction()'s own treatment of an analytical read.

## PRICE_SIGN / OBSERVED_DIRECTION -- Article V2-MR2 (2026-09-15)

Originally `is_real_market_observation()` always returned False: C6
appended its market-reaction claim with `claim_type="FACT"` but no
`evidence_ids`/`financial_fact_ids`, so a real, live-quote-verified
price move fell through to the generic "FACT but no proof" branch and
was silently dropped -- found via a real production specimen (P7-O1's
first live withhold, Sunshine Pictures, 2026-09-15: a genuine, verified
-18.11% same-day move was authorized as UNAVAILABLE purely because
nothing propagated its proof past `context_builder.py`'s own
`MarketReaction`, which at the time only carried `price_move_pct`/
`note`). Traced end to end (MR1) and confirmed: not an integrity issue,
not prose contamination (the claim's own text was already careful and
explicitly non-causal) -- a pure proof-propagation gap between C3 and
P2.

MR2 closed it at the source, not by loosening this check:
`MarketReaction` now also carries `instrument`/`observed_at` (the real
resolved symbol and the real moment `build_article_evidence_bundle`'s
live quote fetch ran), composer.py attaches them to the claim as
`market_observation` (a field deliberately separate from
`evidence_ids`/`financial_fact_ids` -- see `ComposedClaim`'s own
docstring), and `is_real_market_observation()` below checks THAT field
for real presence. Still never inferred from `evidence_ids`/
`financial_fact_ids` being non-empty, from `claim.text`, or from a
section name -- and still requires `claim_type == "FACT"`, so an
INTERPRETATION-typed claim can never reach OBSERVED_DIRECTION even if
some future caller mistakenly attached `market_observation` to one.

## Section-level enforcement — concatenated prose vs. holistic prose

C6's deterministic sections (what_happened, key_details, verified_context,
what_to_watch, source_updated) build their `text` by literally
concatenating each claim's own `text` (composer.py's own docstring: "for
the deterministic sections, by direct concatenation -- there is no
separate step where prose could drift from the claims that justify it").
For these, "drop an UNAVAILABLE claim, never rewrite" is well-defined:
remove the claim, rejoin the survivors' text.

`why_it_matters` is different -- ONE LLM-authored paragraph, not a
concatenation of its `claims` list (composer.py's own docstring: "this
doesn't guarantee the prose and claims are byte-identical"). A single
sentence inside that paragraph cannot be safely excised without
rewriting prose no human/deterministic step has reviewed -- which this
module must never do. So for `why_it_matters` specifically, enforcement
is section-level: if ANY of its claims fails to authorize (UNAVAILABLE),
the WHOLE section is omitted, never partially rewritten. This is a
stronger form of the same "omit, never rewrite" rule, applied at the
granularity that's actually safe for holistic prose.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.article_v2.composer import ComposedClaim, ComposedSection
from app.services.claim_authorization import AuthorizedClaim, Capability, Strength
from app.services.measurement_semantics import IntegrityStatus

# Sections built by literal claim-text concatenation (composer.py's own
# construction) -- safe to excise a single dropped claim from. Any
# section name NOT in this set (today, only "why_it_matters") is treated
# as holistic prose: enforcement omits the whole section instead.
_CONCATENATED_SECTIONS = frozenset({
    "what_happened", "key_details", "verified_context", "what_to_watch", "source_updated",
})


@dataclass(frozen=True)
class TranslationContext:
    """Everything `authorize_composed_claim` needs beyond the claim
    itself. `integrity_status` defaults to VALID because every
    ComposedArticle that successfully returned from `compose_article()`
    already passed a real, structural refusal gate (ComposerRefusal) for
    every degraded input C6 knows how to recognize -- a missing primary
    evidence, a C4 SKIP, a C5 NO_PUBLICATION. There is no fallback/
    degraded path anywhere in the C1-C6 chain that produces a "successful"
    ComposedArticle from bad input; a caller with real reason to believe
    otherwise (a future upstream change) should pass a real, non-default
    value rather than rely on this default silently staying correct."""

    integrity_status: IntegrityStatus = IntegrityStatus.VALID


def is_real_transaction_fact(claim: ComposedClaim) -> bool:
    """Deep Filing Evidence Phase 1C-I (2026-09-17): real, structured
    proof of one POPULATED TransactionFact -- checked on `claim.
    transaction_fact` (composer.py's own dedicated field for this, never
    `evidence_ids`/`financial_fact_ids`, never a `claim.text` substring
    match). Requires `claim_type == "FACT"`, a real value (text or
    numeric), and the full provenance chain (source_document_id, a real
    page_number, a non-empty source_span_text) -- a TransactionFact
    lacking any of these is not proof this module accepts, regardless of
    what its field_code claims. `extraction_status` must be exactly
    POPULATED: a NOT_FOUND row must never reach this function as
    positive evidence in the first place (get_verified_transaction_facts
    already excludes it at the read), but this checks it explicitly
    anyway as a fail-closed backstop, matching this module's own
    "never trust an upstream invariant silently" discipline."""
    if claim.claim_type != "FACT":
        return False
    tf = claim.transaction_fact
    if not tf:
        return False
    if tf.get("extraction_status") != "POPULATED":
        return False
    has_value = tf.get("value_text") is not None or tf.get("value_numeric") is not None
    has_provenance = bool(tf.get("source_document_id")) and tf.get("page_number") is not None and bool(tf.get("source_span_text"))
    return has_value and has_provenance


def is_real_market_observation(claim: ComposedClaim) -> bool:
    """Article V2-MR2 (2026-09-15): real, structured proof of an actual
    market observation -- an instrument, an observation timestamp, and a
    real change_pct, all present on `claim.market_observation` (composer.py's
    own dedicated field for this, never `evidence_ids`/`financial_fact_ids`,
    never a `claim.text` substring match, never a section-name check).
    Also requires `claim_type == "FACT"` -- an observed price move is
    never an interpretation, so an INTERPRETATION-typed claim can never
    reach OBSERVED_DIRECTION through this path even if it somehow carried
    a `market_observation` value."""
    if claim.claim_type != "FACT":
        return False
    mo = claim.market_observation
    if not mo:
        return False
    return bool(mo.get("instrument")) and bool(mo.get("observed_at")) and mo.get("change_pct") is not None


def authorize_composed_claim(claim: ComposedClaim, ctx: TranslationContext) -> AuthorizedClaim:
    """The one real entry point. Never a naive FACT -> AUTHORIZED lookup
    -- routes every claim through claim_authorization.py's real
    capability model. Fail-closed at every unrecognized shape, matching
    claim_authorization.py's own contract exactly."""

    # 1. Integrity status FIRST, unconditionally -- before any claim-shape
    # inspection at all.
    if ctx.integrity_status != IntegrityStatus.VALID:
        return AuthorizedClaim(
            capability=Capability.EVIDENCE_QUALITY, strength=Strength.UNAVAILABLE,
            reason=f"integrity_status={ctx.integrity_status.value}",
        )

    # 2. composer.py's own contract already refuses to emit a claim whose
    # validation_status isn't "VERIFIED" (there is no REJECTED claim in a
    # returned ComposedArticle today) -- checked here anyway as a real,
    # fail-closed backstop, not an assumption that composer.py's
    # invariant will always hold.
    if claim.validation_status != "VERIFIED":
        return AuthorizedClaim(
            capability=Capability.EVIDENCE_QUALITY, strength=Strength.UNAVAILABLE,
            reason=f"claim.validation_status={claim.validation_status!r}, not VERIFIED",
        )

    # 3. A real, structured market observation -- checked on its own real
    # proof, never inferred from evidence_ids/financial_fact_ids being
    # non-empty or from claim.text/section name.
    if is_real_market_observation(claim):
        return AuthorizedClaim(capability=Capability.OBSERVED_DIRECTION, strength=Strength.AUTHORIZED)

    # 3.5. A real, provenance-complete TransactionFact -- HISTORICAL_
    # DESCRIPTION, the same capability an evidence_ids/financial_fact_ids
    # -backed document fact already gets (a filing-derived structured
    # fact IS exactly that kind of fact). Authorizes only the narrow
    # factual proposition composer.py's own template states ("the filing
    # states a stake of 51%") -- never "major acquisition" or any other
    # characterization the fact itself doesn't prove; that judgment is
    # composer.py's phrasing responsibility, not something this
    # authorization step can widen or narrow after the fact.
    if is_real_transaction_fact(claim):
        return AuthorizedClaim(capability=Capability.HISTORICAL_DESCRIPTION, strength=Strength.AUTHORIZED)

    # 4. A verified source/document fact -- DOCUMENTED_FACT, never
    # HISTORICAL_OUTCOME (see claim_provenance.py's own docstring).
    if claim.claim_type == "FACT" and (claim.evidence_ids or claim.financial_fact_ids):
        return AuthorizedClaim(capability=Capability.HISTORICAL_DESCRIPTION, strength=Strength.AUTHORIZED)

    # 5. A FACT-typed claim with neither evidence_ids nor
    # financial_fact_ids is an upstream contract violation -- fail
    # closed rather than trust the claim_type label alone.
    if claim.claim_type == "FACT":
        return AuthorizedClaim(
            capability=Capability.EVIDENCE_QUALITY, strength=Strength.UNAVAILABLE,
            reason="claim_type=FACT but no evidence_ids/financial_fact_ids",
        )

    # 6. INTERPRETATION is always QUALIFIED, never AUTHORIZED and never
    # rejected outright.
    if claim.claim_type == "INTERPRETATION":
        return AuthorizedClaim(capability=Capability.ANALYTICAL_HYPOTHESIS, strength=Strength.QUALIFIED)

    # 7. Never infer a stronger claim from an unrecognized shape.
    return AuthorizedClaim(
        capability=Capability.EVIDENCE_QUALITY, strength=Strength.UNAVAILABLE,
        reason=f"unclassified claim_type={claim.claim_type!r}",
    )


@dataclass(frozen=True)
class SectionEnforcementResult:
    section: ComposedSection | None  # None when the whole section was omitted
    dropped_claims: list[ComposedClaim]
    authorizations: list[AuthorizedClaim]  # one per SURVIVING claim, same order as section.claims


def enforce_section_authorization(section: ComposedSection, ctx: TranslationContext) -> SectionEnforcementResult:
    """Authorizes every claim in one section and applies the "omit,
    never rewrite" rule at the granularity that's actually safe for that
    section's own construction (see this module's docstring). A section
    with zero claims to begin with (source_updated) passes through
    unchanged -- there is nothing to authorize or drop."""
    if not section.claims:
        return SectionEnforcementResult(section=section, dropped_claims=[], authorizations=[])

    decisions = [(claim, authorize_composed_claim(claim, ctx)) for claim in section.claims]
    survivors = [(claim, dec) for claim, dec in decisions if dec.strength != Strength.UNAVAILABLE]
    dropped = [claim for claim, dec in decisions if dec.strength == Strength.UNAVAILABLE]

    if not dropped:
        return SectionEnforcementResult(
            section=section, dropped_claims=[], authorizations=[dec for _, dec in decisions],
        )

    if section.name not in _CONCATENATED_SECTIONS:
        # Holistic prose (why_it_matters): any single unauthorized claim
        # omits the WHOLE section rather than rewriting the paragraph
        # around it -- so EVERY claim in the section is "dropped" from
        # the final output here, including one that individually would
        # have authorized fine; it never survives on its own once the
        # section itself is omitted.
        return SectionEnforcementResult(section=None, dropped_claims=list(section.claims), authorizations=[])

    if not survivors:
        # Every claim in a concatenated section was dropped -- nothing
        # left to render, the section is omitted (never an empty shell).
        return SectionEnforcementResult(section=None, dropped_claims=dropped, authorizations=[])

    surviving_claims = [claim for claim, _ in survivors]
    rebuilt_text = " ".join(c.text for c in surviving_claims)
    rebuilt = ComposedSection(name=section.name, text=rebuilt_text, claims=surviving_claims)
    return SectionEnforcementResult(
        section=rebuilt, dropped_claims=dropped, authorizations=[dec for _, dec in survivors],
    )

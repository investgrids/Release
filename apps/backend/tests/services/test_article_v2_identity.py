"""
Article V2 Phase C5.1/C5.2 — Identity + Uniqueness tests. Pure functions
over ArticleEvidenceSet/LinkedEvidence, constructed directly (matching
the C3/C4 test convention). Covers the owner's own real examples
verbatim.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.identity import (
    CREATE_NEW, NO_PUBLICATION, UPDATE_EXISTING, compute_identity, resolve_uniqueness,
)
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, days_ago: int = 0) -> LinkedEvidence:
    now = datetime.now(timezone.utc)
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type="nse",
        published_at=now - timedelta(days=days_ago), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _es(entity_id: str, symbol: str, primary_title: str, days_ago: int = 0) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=entity_id, symbol=symbol, event_id="evt", event_headline=primary_title,
        status="COHERENT", primary_evidence=_evidence(primary_title, days_ago=days_ago),
    )


def test_same_development_differently_worded_evidence_shares_identity():
    """The owner's own real example, verbatim."""
    e1 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding a press release: ABC wins Rs 800 crore railway order")
    e2 = _es("cmp_abc", "ABC", "ABC has informed the Exchange: ABC receives LoA for Rs 800 crore railway project")
    e3 = _es("cmp_abc", "ABC", "ABC has informed the Exchange: ABC confirms Rs 800 crore order in exchange filing")
    id1, id2, id3 = compute_identity(e1), compute_identity(e2), compute_identity(e3)
    assert id1.identity_key == id2.identity_key == id3.identity_key


def test_same_company_different_order_two_months_later_gets_different_identity():
    """The owner's own real contrasting example: same entity, same
    development_type, but a genuinely different order -- different
    anchor AND different time window -- must be a DIFFERENT identity."""
    e1 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding a press release: ABC wins Rs 800 crore railway order", days_ago=60)
    e2 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding a press release: ABC wins another Rs 450 crore defence order", days_ago=0)
    id1, id2 = compute_identity(e1), compute_identity(e2)
    assert id1.identity_key != id2.identity_key
    assert id1.anchor != id2.anchor
    assert id1.time_bucket != id2.time_bucket


def test_same_company_genuinely_different_development_type_gets_different_identity():
    e1 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding a press release: ABC wins Rs 800 crore railway order")
    e2 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding resignation of an Independent Director")
    id1, id2 = compute_identity(e1), compute_identity(e2)
    assert id1.identity_key != id2.identity_key
    assert id1.development_type != id2.development_type


def test_different_company_same_development_text_gets_different_identity():
    """Canonical entity is part of the identity key -- two different
    companies reporting a structurally similar development must never
    collide."""
    e1 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding resignation of an Independent Director")
    e2 = _es("cmp_xyz", "XYZ", "XYZ has informed the Exchange regarding resignation of an Independent Director")
    id1, id2 = compute_identity(e1), compute_identity(e2)
    assert id1.identity_key != id2.identity_key


def test_c4_update_existing_is_preserved_as_the_canonical_url():
    es = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding updated fundraising terms")
    identity = compute_identity(es)
    resolution = resolve_uniqueness(
        identity, c4_publication_action="UPDATE_EXISTING", c4_matched_article_id="art_999", known_identities={},
    )
    assert resolution.publication_action == UPDATE_EXISTING
    assert resolution.matched_article_id == "art_999"


def test_c4_none_becomes_no_publication():
    es = _es("cmp_abc", "ABC", "ABC has informed the Exchange about Copy of Newspaper Publication")
    identity = compute_identity(es)
    resolution = resolve_uniqueness(
        identity, c4_publication_action="NONE", c4_matched_article_id=None, known_identities={},
    )
    assert resolution.publication_action == NO_PUBLICATION


def test_first_seen_identity_in_batch_gets_create_new_second_gets_no_publication():
    """The owner's own hard rule: one underlying development must not
    produce two canonical URLs within the same processing batch, even
    if two different triggering events independently reached C4=CREATE."""
    es1 = _es("cmp_abc", "ABC", "ABC has informed the Exchange regarding a press release: ABC wins Rs 800 crore railway order")
    es2 = _es("cmp_abc", "ABC", "ABC has informed the Exchange: ABC confirms Rs 800 crore order in exchange filing")
    id1, id2 = compute_identity(es1), compute_identity(es2)
    assert id1.identity_key == id2.identity_key  # same real development

    known: dict[str, str] = {}
    res1 = resolve_uniqueness(id1, c4_publication_action="CREATE", c4_matched_article_id=None, known_identities=known)
    assert res1.publication_action == CREATE_NEW
    known[id1.identity_key] = "ABC-batch-item-1"

    res2 = resolve_uniqueness(id2, c4_publication_action="CREATE", c4_matched_article_id=None, known_identities=known)
    assert res2.publication_action == NO_PUBLICATION
    assert res2.matched_article_id == "ABC-batch-item-1"

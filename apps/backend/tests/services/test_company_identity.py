"""
Company Identity C2 — real, DB-backed tests proving the specific cases the
C1 reconciliation found (see artifacts/company_identity_c1_reconciliation.md)
resolve correctly, and that the importer is genuinely idempotent.

Fixtures (tests/fixtures/company_identity/) use real, verified data where
independently confirmed this session:
  - nse_eq_sample.csv: RELIANCE/TCS/CEATLTD/HINDPETRO/IOC/AUROPHARMA/TMPV/
    TMCV are real rows (symbol, name, ISIN, listing date all copied
    verbatim from a live NSE EQUITY_L.csv fetch). LTIM's ISIN
    ("INE214TFIXTURE") is a clearly-marked SYNTHETIC placeholder — LTIM's
    real ISIN was not independently verified this session (LTIMindtree
    was confirmed absent from the live EQUITY_L.csv snapshot pulled
    2026-08-24, a real, reported data-source gap; only the LTI->LTIM
    RENAME event itself is independently verified, via symbolchange.csv).
  - nse_symbolchange_sample.csv: all 3 rows copied verbatim from NSE's
    real symbolchange.csv (fetched 2026-08-24).

One deliberate correction from the owner's own completion-gate wording:
"MINDTREE -> LTIMINDTREE" is NOT a rename — NSE's symbolchange.csv has no
MINDTREE row at all. Real picture: Larsen & Toubro Infotech (symbol LTI)
merged with the separate company Mindtree Limited and renamed itself
LTIMindtree (LTI -> LTIM, 05-DEC-2022) — an amalgamation, where Mindtree's
own distinct ISIN/entity was absorbed, not simply renamed. Modeling
"MINDTREE" as an old_symbol alias of the LTIM entity would misrepresent
that history (pre-merger, they were two separate real companies) the same
way a fuzzy-matched guess would. This suite tests the real, verified
LTI->LTIM rename instead, which is the structurally correct analog to the
TATAMOTORS->TMPV case.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import delete, select

from app.db.models.company_entity import CompanyEntity, CompanyAlias
from app.db.session import AsyncSessionLocal
from app.services.company_identity.classifier import IdentifierType, classify_identifier
from app.services.company_identity.resolver import ResolutionStatus, resolve_identifier
from app.services.company_identity.importer import (
    parse_nse_eq_csv, parse_nse_symbolchange_csv, upsert_company_entities,
    apply_symbol_change_aliases, apply_known_provider_aliases, run_full_import,
)

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "company_identity")


def _read_fixture(name: str) -> str:
    with open(os.path.join(_FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


EQ_CSV = _read_fixture("nse_eq_sample.csv")
SYMBOLCHANGE_CSV = _read_fixture("nse_symbolchange_sample.csv")

_FIXTURE_ISINS = [
    "INE002A01018", "INE467B01029", "INE482A01020", "INE094A01015",
    "INE242A01010", "INE406A01037", "INE155A01022", "INE1TAE01010",
    "INE214TFIXTURE",
]


_FIXTURE_ALIAS_VALUES = [
    # Every symbol/old_symbol/provider_symbol text this fixture's own EQ/
    # symbolchange CSVs use. Real, reproducible bug this closes: a real C2
    # import run against the same DB (done during this session's live
    # verification) creates its own real LTIM entity with its own real
    # ISIN -- not in _FIXTURE_ISINS, so it survived cleanup-by-ISIN -- and
    # that real entity's own real "LTI" old_symbol alias then collided
    # with this fixture's "LTI" alias (pointing at the fixture's
    # fake-ISIN LTIM), producing two distinct entity_ids for the same
    # alias value -> a genuine CONFLICT, not a resolver defect (the
    # resolver correctly refused to guess between them). Cleaning by
    # alias VALUE as well as by fixture ISIN makes this fixture immune to
    # whatever real data happens to already be sitting in the DB.
    "RELIANCE", "TCS", "CEATLTD", "HINDPETRO", "IOC", "AUROPHARMA",
    "TMPV", "TMCV", "LTIM", "TELCO", "TATAMOTORS", "LTI",
    "CEAT", "HPCL", "IOCL", "AUROBINDOPHARMA",
]


async def _clean_fixture_rows(db):
    entity_ids = set((await db.execute(
        select(CompanyEntity.entity_id).where(CompanyEntity.isin.in_(_FIXTURE_ISINS))
    )).scalars().all())
    entity_ids |= set((await db.execute(
        select(CompanyEntity.entity_id).where(CompanyEntity.symbol.in_(_FIXTURE_ALIAS_VALUES))
    )).scalars().all())
    entity_ids |= set((await db.execute(
        select(CompanyAlias.entity_id).where(CompanyAlias.alias_value.in_(_FIXTURE_ALIAS_VALUES))
    )).scalars().all())
    if entity_ids:
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.commit()


@pytest.fixture
async def seeded_db():
    """Runs the real importer against the real fixture CSVs, yields nothing
    (tests query fresh sessions themselves — matches this repo's own
    established async-session-per-operation convention), cleans up after."""
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()
    yield
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)


# ── Classifier: type protection ─────────────────────────────────────────────

def test_index_identifiers_never_classify_as_company():
    for raw in ["^NSEI", "^BSESN", "BANK_NIFTY", "BANKEX", "NIFTY", "NSE:BSESENSEX"]:
        assert classify_identifier(raw) != IdentifierType.COMPANY, raw


def test_currency_and_bond_identifiers_never_classify_as_company():
    for raw in ["USDINR", "GOI10YR", "10YBENCH", "GSEC", "GOI10YT=RR"]:
        assert classify_identifier(raw) != IdentifierType.COMPANY, raw


def test_commodity_identifiers_never_classify_as_company():
    for raw in ["CRUDEOIL", "GOLD", "SILVER"]:
        assert classify_identifier(raw) != IdentifierType.COMPANY, raw


def test_self_referential_exchange_prefixes_are_not_a_company():
    for raw in ["NSE:NSE", "BSE:BSE", "MCX:MCX", "NSE:BSE"]:
        assert classify_identifier(raw) != IdentifierType.COMPANY, raw


def test_real_ticker_shapes_classify_as_company_candidate():
    for raw in ["RELIANCE", "RELIANCE.NS", "NSE:RELIANCE", "TCS"]:
        assert classify_identifier(raw) == IdentifierType.COMPANY, raw


# ── Resolver: variants resolve identically, unknowns never auto-create ─────

@pytest.mark.asyncio
async def test_reliance_ns_and_nse_prefix_variants_resolve_to_the_same_entity(seeded_db):
    async with AsyncSessionLocal() as db:
        bare = await resolve_identifier(db, "RELIANCE")
        dotns = await resolve_identifier(db, "RELIANCE.NS")
        prefixed = await resolve_identifier(db, "NSE:RELIANCE")
    assert bare.status == dotns.status == prefixed.status == ResolutionStatus.RESOLVED
    assert bare.entity_id == dotns.entity_id == prefixed.entity_id


@pytest.mark.asyncio
async def test_triple_node_case_resolves_to_one_entity_id(seeded_db):
    """The real C1 finding: RELIANCE had 3 distinct graph node variants
    (company:reliance, company:reliance-ns, company:nse-reliance). All 3
    raw forms must resolve to the same entity_id."""
    async with AsyncSessionLocal() as db:
        results = [await resolve_identifier(db, raw) for raw in
                   ["company:reliance".split(":")[-1], "RELIANCE.NS", "NSE:RELIANCE"]]
    entity_ids = {r.entity_id for r in results}
    assert all(r.status == ResolutionStatus.RESOLVED for r in results)
    assert len(entity_ids) == 1


@pytest.mark.asyncio
async def test_unknown_identifier_does_not_auto_create_a_company(seeded_db):
    async with AsyncSessionLocal() as db:
        before = len((await db.execute(select(CompanyEntity))).scalars().all())
        result = await resolve_identifier(db, "MADEUPTICKERXYZ123")
        after = len((await db.execute(select(CompanyEntity))).scalars().all())
    assert result.status == ResolutionStatus.UNRESOLVED
    assert after == before  # resolver never writes


@pytest.mark.asyncio
async def test_index_fx_bond_examples_do_not_become_company_entities(seeded_db):
    async with AsyncSessionLocal() as db:
        for raw in ["^NSEI", "USDINR", "GOI10YR", "BANK_NIFTY"]:
            result = await resolve_identifier(db, raw)
            assert result.status == ResolutionStatus.NOT_A_COMPANY, raw
            assert result.entity_id is None


# ── Real corporate-action history ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_tatamotors_resolves_through_history_to_tmpv(seeded_db):
    """Real, NSE-sourced chain: TELCO -> TATAMOTORS (26-DEC-2003) ->
    TMPV (24-OCT-2025). The old symbol must still resolve — corporate
    history isn't lost — and it must resolve to TMPV's entity, not a
    fabricated new one."""
    async with AsyncSessionLocal() as db:
        old = await resolve_identifier(db, "TATAMOTORS")
        older = await resolve_identifier(db, "TELCO")
        current = await resolve_identifier(db, "TMPV")
    assert old.status == ResolutionStatus.RESOLVED
    assert older.status == ResolutionStatus.RESOLVED
    assert current.status == ResolutionStatus.RESOLVED
    assert old.entity_id == older.entity_id == current.entity_id
    assert old.matched_alias_type == "old_symbol"
    assert older.matched_alias_type == "old_symbol"
    assert current.matched_alias_type == "symbol"


@pytest.mark.asyncio
async def test_tmcv_is_a_distinct_entity_not_merged_with_tmpv(seeded_db):
    """The demerger produced TWO real, distinct entities (TMPV keeps the
    original ISIN under a new symbol; TMCV is a brand-new ISIN/listing).
    They must NOT resolve to the same entity_id — that would silently
    merge two different real companies."""
    async with AsyncSessionLocal() as db:
        tmpv = await resolve_identifier(db, "TMPV")
        tmcv = await resolve_identifier(db, "TMCV")
    assert tmpv.status == tmcv.status == ResolutionStatus.RESOLVED
    assert tmpv.entity_id != tmcv.entity_id


@pytest.mark.asyncio
async def test_lti_renamed_to_ltim_resolves_through_history(seeded_db):
    """Real, NSE-sourced rename (05-DEC-2022), independently verified via
    symbolchange.csv — the structurally-correct analog to TATAMOTORS/TMPV
    that the completion gate's own 'MINDTREE -> LTIMINDTREE' wording was
    actually reaching for (see this file's module docstring for why
    MINDTREE itself is a merger, not a rename, and isn't tested here)."""
    async with AsyncSessionLocal() as db:
        old = await resolve_identifier(db, "LTI")
        current = await resolve_identifier(db, "LTIM")
    assert old.status == current.status == ResolutionStatus.RESOLVED
    assert old.entity_id == current.entity_id
    assert old.matched_alias_type == "old_symbol"


# ── Provider/vendor ticker variants — sourced aliases only, no fuzzy match ──

@pytest.mark.asyncio
async def test_ceat_hpcl_iocl_resolve_only_through_sourced_provider_aliases(seeded_db):
    async with AsyncSessionLocal() as db:
        ceat = await resolve_identifier(db, "CEAT")
        ceatltd = await resolve_identifier(db, "CEATLTD")
        hpcl = await resolve_identifier(db, "HPCL")
        hindpetro = await resolve_identifier(db, "HINDPETRO")
        iocl = await resolve_identifier(db, "IOCL")
        ioc = await resolve_identifier(db, "IOC")
    assert ceat.status == ResolutionStatus.RESOLVED and ceat.entity_id == ceatltd.entity_id
    assert ceat.matched_alias_type == "provider_symbol"
    assert hpcl.status == ResolutionStatus.RESOLVED and hpcl.entity_id == hindpetro.entity_id
    assert hpcl.matched_alias_type == "provider_symbol"
    assert iocl.status == ResolutionStatus.RESOLVED and iocl.entity_id == ioc.entity_id
    assert iocl.matched_alias_type == "provider_symbol"


@pytest.mark.asyncio
async def test_provider_alias_is_never_created_for_an_unmatched_string(seeded_db):
    """apply_known_provider_aliases only attaches to a real, already-
    resolved entity — a made-up pair must not silently create anything."""
    from app.services.company_identity.importer import apply_known_provider_aliases
    async with AsyncSessionLocal() as db:
        before = len((await db.execute(select(CompanyAlias))).scalars().all())
        summary = await apply_known_provider_aliases(
            db, pairs=(("FAKEPROVIDER", "NOSUCHREALSYMBOLXYZ"),),
        )
        await db.commit()
        after = len((await db.execute(select(CompanyAlias))).scalars().all())
    assert summary.old_symbol_aliases_created == 0
    assert after == before


# ── ISIN uniqueness / collision behavior ────────────────────────────────────

@pytest.mark.asyncio
async def test_isin_is_unique_across_entities(seeded_db):
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(CompanyEntity.isin).where(CompanyEntity.isin.in_(_FIXTURE_ISINS))
        )).scalars().all()
    assert len(rows) == len(set(rows))


@pytest.mark.asyncio
async def test_same_run_isin_collision_is_reported_not_silently_dropped():
    rows = parse_nse_eq_csv(EQ_CSV) + parse_nse_eq_csv(EQ_CSV.replace("RELIANCE", "RELIANCEDUP"))
    # force a real collision: two different symbols claiming RELIANCE's ISIN
    from app.services.company_identity.importer import NseEqRow
    collided = rows + [NseEqRow(symbol="RELIANCEFAKE", name="Fake", series="EQ", isin="INE002A01018", listing_date=None)]
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        summary = await upsert_company_entities(db, collided)
        await db.rollback()
    assert len(summary.isin_collisions) >= 1
    assert summary.isin_collisions[0]["isin"] == "INE002A01018"


# ── Idempotent seed/upsert ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rerunning_the_full_import_creates_zero_duplicate_entities():
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        first = await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()

    async with AsyncSessionLocal() as db:
        second = await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()

    async with AsyncSessionLocal() as db:
        entities = (await db.execute(
            select(CompanyEntity).where(CompanyEntity.isin.in_(_FIXTURE_ISINS))
        )).scalars().all()
        await _clean_fixture_rows(db)

    assert first["eq_import"]["canonical_entities_created"] == len(_FIXTURE_ISINS)
    assert second["eq_import"]["canonical_entities_created"] == 0
    assert second["eq_import"]["canonical_entities_unchanged"] == len(_FIXTURE_ISINS)
    assert len(entities) == len(_FIXTURE_ISINS)  # no duplicates after 2 runs


@pytest.mark.asyncio
async def test_full_import_reconciliation_output_shape():
    """The exact accounting the owner asked for: rows -> entities -> ISINs
    -> aliases -> unresolved/conflicts, nothing silently dropped."""
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        result = await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()
        await _clean_fixture_rows(db)

    eq = result["eq_import"]
    assert eq["eq_rows_processed"] == 9
    assert eq["canonical_entities_created"] == 9
    assert eq["unique_isins"] == 9
    assert eq["isin_collisions"] == []

    sc = result["symbol_change_import"]
    # TELCO, TATAMOTORS both resolve to TMPV; LTI resolves to LTIM — 3 real
    # old_symbol aliases created, zero skipped as unresolvable.
    assert sc["old_symbol_aliases_created"] == 3
    assert sc["old_symbol_rows_skipped_no_target"] == 0

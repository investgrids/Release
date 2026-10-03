"""
HEG -> HEGAM (2026-10-03): the Company Master kept a renamed company under
its old symbol, so its page said "not found". Renames are applied only when
NSE lists the new symbol with the SAME ISIN, never by symbol alone.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import delete, select

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import NseEqRow, SymbolChangeRow
from app.services.company_identity.qualification import resolve_entity_by_any_symbol
from app.services.company_identity.renames import apply_verified_renames


def _tag() -> str:
    return "Z" + uuid.uuid4().hex[:6].upper()


async def _seed(db, symbol: str, isin: str) -> str:
    e = CompanyEntity(company_name=f"{symbol} Limited", isin=isin, exchange="NSE", symbol=symbol,
                      series="EQ", listing_status="active", listing_date=date(1995, 5, 10), source="test")
    db.add(e)
    await db.flush()
    db.add(CompanyAlias(entity_id=e.entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE",
                        valid_from=date(1995, 5, 10), valid_to=None, source="test"))
    await db.commit()
    return e.entity_id


async def _cleanup(entity_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.commit()


def _eq(symbol, isin, name="Renamed Co Limited"):
    return NseEqRow(symbol=symbol, name=name, series="EQ", isin=isin, listing_date=date(1995, 5, 10))


def _chg(old, new):
    return SymbolChangeRow(company_name="x", old_symbol=old, new_symbol=new, change_date=date(2026, 9, 22))


@pytest.mark.asyncio
async def test_same_isin_rename_is_applied_and_both_symbols_resolve_to_one_entity():
    old, new, isin = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    async with AsyncSessionLocal() as db:
        entity_id = await _seed(db, old, isin)
    try:
        async with AsyncSessionLocal() as db:
            result = await apply_verified_renames(db, [_eq(new, isin)], [_chg(old, new)], apply=True)
        assert result["applied"] is True and result["renames"] == 1
        async with AsyncSessionLocal() as db:
            by_new = await resolve_entity_by_any_symbol(db, new)
            by_old = await resolve_entity_by_any_symbol(db, old)
            assert by_new is not None and by_new.entity_id == entity_id
            assert by_new.symbol == new  # canonical symbol is now the new one
            assert by_old is not None and by_old.entity_id == entity_id  # old URL still reaches it
            assert (await db.execute(select(CompanyEntity).where(CompanyEntity.isin == isin))).scalars().all().__len__() == 1
    finally:
        await _cleanup([entity_id])


@pytest.mark.asyncio
async def test_dry_run_changes_nothing_but_reports_the_plan():
    old, new, isin = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    async with AsyncSessionLocal() as db:
        entity_id = await _seed(db, old, isin)
    try:
        async with AsyncSessionLocal() as db:
            result = await apply_verified_renames(db, [_eq(new, isin)], [_chg(old, new)], apply=False)
        assert result["applied"] is False and result["renames"] == 1
        assert result["plan"][0]["old_symbol"] == old and result["plan"][0]["new_symbol"] == new
        async with AsyncSessionLocal() as db:
            ent = (await db.execute(select(CompanyEntity).where(CompanyEntity.entity_id == entity_id))).scalars().one()
            assert ent.symbol == old
    finally:
        await _cleanup([entity_id])


@pytest.mark.asyncio
async def test_isin_mismatch_is_skipped_a_reused_symbol_is_never_renamed_by_name_alone():
    old, new = _tag(), _tag()
    async with AsyncSessionLocal() as db:
        entity_id = await _seed(db, old, "INE000000001")
    try:
        async with AsyncSessionLocal() as db:
            result = await apply_verified_renames(db, [_eq(new, "INE999999999")], [_chg(old, new)], apply=True)
        assert result["renames"] == 0 and result["applied"] is False
        assert "ISIN" in result["plan"][0]["reason"]
        async with AsyncSessionLocal() as db:
            ent = (await db.execute(select(CompanyEntity).where(CompanyEntity.entity_id == entity_id))).scalars().one()
            assert ent.symbol == old
    finally:
        await _cleanup([entity_id])


@pytest.mark.asyncio
async def test_new_symbol_already_owned_by_another_entity_is_skipped():
    old, new, isin = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    async with AsyncSessionLocal() as db:
        a = await _seed(db, old, isin)
        b = await _seed(db, new, "INE000000002")
    try:
        async with AsyncSessionLocal() as db:
            result = await apply_verified_renames(db, [_eq(new, isin)], [_chg(old, new)], apply=True)
        assert result["renames"] == 0
        assert "another entity" in result["plan"][0]["reason"]
    finally:
        await _cleanup([a, b])


@pytest.mark.asyncio
async def test_applying_twice_is_idempotent():
    old, new, isin = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    async with AsyncSessionLocal() as db:
        entity_id = await _seed(db, old, isin)
    try:
        for _ in range(2):
            async with AsyncSessionLocal() as db:
                await apply_verified_renames(db, [_eq(new, isin)], [_chg(old, new)], apply=True)
        async with AsyncSessionLocal() as db:
            ents = (await db.execute(select(CompanyEntity).where(CompanyEntity.isin == isin))).scalars().all()
            assert len(ents) == 1 and ents[0].symbol == new
            old_aliases = (await db.execute(select(CompanyAlias).where(
                CompanyAlias.entity_id == entity_id, CompanyAlias.alias_type == "old_symbol", CompanyAlias.alias_value == old))).scalars().all()
            assert len(old_aliases) == 1
    finally:
        await _cleanup([entity_id])


@pytest.mark.asyncio
async def test_entity_not_held_under_the_old_symbol_is_ignored():
    result = None
    async with AsyncSessionLocal() as db:
        result = await apply_verified_renames(db, [_eq("NEWX", "INE111111111")], [_chg("NOSUCHOLD", "NEWX")], apply=True)
    assert result["renames"] == 0 and result["plan"] == []


@pytest.mark.asyncio
async def test_only_filter_applies_just_the_selected_old_symbols_and_reports_the_rest():
    o1, n1, i1 = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    o2, n2, i2 = _tag(), _tag(), f"INE{uuid.uuid4().hex[:9].upper()}"
    async with AsyncSessionLocal() as db:
        e1 = await _seed(db, o1, i1)
        e2 = await _seed(db, o2, i2)
    try:
        async with AsyncSessionLocal() as db:
            result = await apply_verified_renames(db, [_eq(n1, i1), _eq(n2, i2)], [_chg(o1, n1), _chg(o2, n2)],
                                                  apply=True, only={o1})
        assert result["renames"] == 1 and result["pending_not_selected"] == 1
        async with AsyncSessionLocal() as db:
            assert (await db.execute(select(CompanyEntity).where(CompanyEntity.entity_id == e1))).scalars().one().symbol == n1
            assert (await db.execute(select(CompanyEntity).where(CompanyEntity.entity_id == e2))).scalars().one().symbol == o2
    finally:
        await _cleanup([e1, e2])

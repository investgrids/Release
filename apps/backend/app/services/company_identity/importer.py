"""
Idempotent Company Master importer.

Two real, primary NSE sources, kept as two separate concerns:

  parse_nse_eq_csv()          — NSE's live main-board EQUITY_L.csv. Current
                                 state only: symbol, name, series, ISIN,
                                 listing date. This is the ONLY thing
                                 allowed to create a new CompanyEntity row.

  parse_nse_symbolchange_csv() — NSE's own symbolchange.csv: real, dated
                                 historical renames (company name, old
                                 symbol, new symbol, date). Used only to
                                 backfill `old_symbol` CompanyAlias rows on
                                 an entity that the EQ import already
                                 created — never to create a new entity on
                                 its own. A rename chain (TELCO ->
                                 TATAMOTORS -> TMPV) becomes two old_symbol
                                 aliases on TMPV's entity_id, each dated to
                                 its own real window; a chain whose final
                                 symbol never made it into the current EQ
                                 import (e.g. a fund renamed, or the target
                                 company genuinely isn't in this run's EQ
                                 snapshot) is skipped, not guessed at — see
                                 apply_symbol_change_aliases()'s own
                                 docstring for why this matters in practice
                                 (a real, confirmed gap: LTIMindtree's
                                 LTI->LTIM rename is real and NSE-sourced,
                                 but LTIM itself was absent from the
                                 EQUITY_L.csv snapshot pulled 2026-08-24 —
                                 see artifacts/company_identity_c1_reconciliation.md).

Both entry points take already-fetched CSV text, not a URL — the live
HTTP fetch is a thin, separate, untested-by-design wrapper
(app.services.company_identity.live_source) so the parsing/upsert logic
itself is fully testable against real, fixed fixture text without
depending on network access or NSE's own uptime.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity, CompanyAlias
from app.services.company_identity.classifier import normalize_identifier


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class NseEqRow:
    symbol: str
    name: str
    series: str
    isin: str | None
    listing_date: date | None


@dataclass
class SymbolChangeRow:
    company_name: str
    old_symbol: str
    new_symbol: str
    change_date: date


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d-%b-%Y").date()
    except ValueError:
        return None


def parse_nse_eq_csv(text: str) -> list[NseEqRow]:
    """EQUITY_L.csv columns: SYMBOL, NAME OF COMPANY, SERIES,
    DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE.
    Real header has leading spaces on every column after the first —
    normalize before matching. Only EQ-series rows are real, currently
    tradeable equity — BE (trade-to-trade)/BZ (suspended) are handled by
    the caller if it ever wants them; this parser returns everything and
    lets the caller filter, since "which series count as the core
    universe" is a policy decision, not a parsing one."""
    reader = csv.DictReader(io.StringIO(text))
    rows: list[NseEqRow] = []
    for r in reader:
        norm = {k.strip().upper(): (v or "").strip() for k, v in r.items()}
        symbol = norm.get("SYMBOL", "")
        if not symbol:
            continue
        rows.append(NseEqRow(
            symbol=symbol,
            name=norm.get("NAME OF COMPANY", ""),
            series=norm.get("SERIES", ""),
            isin=norm.get("ISIN NUMBER") or None,
            listing_date=_parse_date(norm.get("DATE OF LISTING", "")),
        ))
    return rows


def parse_nse_symbolchange_csv(text: str) -> list[SymbolChangeRow]:
    """symbolchange.csv has NO header row: company name, old symbol, new
    symbol, date — one rename event per row. Includes a lot of non-equity
    noise (mutual fund plan renames dominate the real file); this parser
    returns every row as-is and leaves filtering to
    apply_symbol_change_aliases(), which only keeps a row whose new_symbol
    resolves to a real entity the EQ import already created."""
    reader = csv.reader(io.StringIO(text))
    rows: list[SymbolChangeRow] = []
    for r in reader:
        if len(r) < 4:
            continue
        name, old_sym, new_sym, dt = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
        d = _parse_date(dt)
        if not old_sym or not new_sym or d is None:
            continue
        rows.append(SymbolChangeRow(company_name=name, old_symbol=old_sym, new_symbol=new_sym, change_date=d))
    return rows


@dataclass
class ImportSummary:
    eq_rows_processed: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    entities_unchanged: int = 0
    unique_isins: int = 0
    rows_missing_isin: int = 0
    isin_collisions: list[dict[str, Any]] = field(default_factory=list)
    symbol_aliases_created: int = 0
    old_symbol_aliases_created: int = 0
    old_symbol_rows_skipped_no_target: int = 0
    old_symbol_rows_skipped_ambiguous: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "eq_rows_processed": self.eq_rows_processed,
            "canonical_entities_created": self.entities_created,
            "canonical_entities_updated": self.entities_updated,
            "canonical_entities_unchanged": self.entities_unchanged,
            "unique_isins": self.unique_isins,
            "rows_missing_isin": self.rows_missing_isin,
            "isin_collisions": self.isin_collisions,
            "symbol_aliases_created": self.symbol_aliases_created,
            "old_symbol_aliases_created": self.old_symbol_aliases_created,
            "old_symbol_rows_skipped_no_target": self.old_symbol_rows_skipped_no_target,
            "old_symbol_rows_skipped_ambiguous": self.old_symbol_rows_skipped_ambiguous,
        }


async def _get_current_symbol_alias(db: AsyncSession, entity_id: str) -> CompanyAlias | None:
    return (await db.execute(
        select(CompanyAlias).where(
            CompanyAlias.entity_id == entity_id,
            CompanyAlias.alias_type == "symbol",
            CompanyAlias.valid_to.is_(None),
        )
    )).scalars().first()


async def upsert_company_entities(
    db: AsyncSession, rows: list[NseEqRow], *, source: str = "nse_eq_l", allowed_series: set[str] | None = None,
) -> ImportSummary:
    """Idempotent: matches by ISIN first (the real stable identity key),
    falling back to (symbol, exchange) only when ISIN is missing. Rerunning
    with the same input creates zero new entities and zero duplicate
    'symbol' aliases — every field is compared before writing, and an
    unchanged row is counted, not re-saved."""
    summary = ImportSummary()
    seen_isins: dict[str, str] = {}  # isin -> symbol, within THIS run — catches a same-run collision

    for row in rows:
        if allowed_series is not None and row.series not in allowed_series:
            continue
        summary.eq_rows_processed += 1

        if not row.isin:
            summary.rows_missing_isin += 1
            existing = (await db.execute(
                select(CompanyEntity).where(
                    CompanyEntity.symbol == row.symbol, CompanyEntity.exchange == "NSE", CompanyEntity.isin.is_(None),
                )
            )).scalars().first()
        else:
            if row.isin in seen_isins and seen_isins[row.isin] != row.symbol:
                summary.isin_collisions.append({
                    "isin": row.isin, "symbols_in_this_run": [seen_isins[row.isin], row.symbol],
                })
                continue
            seen_isins[row.isin] = row.symbol
            existing = (await db.execute(
                select(CompanyEntity).where(CompanyEntity.isin == row.isin)
            )).scalars().first()

        if existing is None:
            entity = CompanyEntity(
                company_name=row.name, isin=row.isin, exchange="NSE", symbol=row.symbol,
                series=row.series, listing_status="active", listing_date=row.listing_date,
                source=source, source_updated_at=_now(),
            )
            db.add(entity)
            await db.flush()
            summary.entities_created += 1
            db.add(CompanyAlias(
                entity_id=entity.entity_id, alias_type="symbol", alias_value=row.symbol,
                exchange="NSE", valid_from=row.listing_date, valid_to=None, source=source,
            ))
            summary.symbol_aliases_created += 1
            continue

        current_alias = await _get_current_symbol_alias(db, existing.entity_id)
        symbol_changed = existing.symbol != row.symbol
        name_changed = existing.company_name != row.name
        series_changed = existing.series != row.series

        if symbol_changed or name_changed or series_changed:
            if symbol_changed:
                # Real corporate action inside this import itself (the same
                # ISIN now carries a different symbol than last run) — close
                # out the old 'symbol' alias and open a new one, rather than
                # mutating alias_value in place and losing the history.
                if current_alias is not None and current_alias.alias_value != row.symbol:
                    current_alias.valid_to = row.listing_date or date.today()
                    db.add(CompanyAlias(
                        entity_id=existing.entity_id, alias_type="symbol", alias_value=row.symbol,
                        exchange="NSE", valid_from=current_alias.valid_to, valid_to=None, source=source,
                    ))
                    summary.symbol_aliases_created += 1
            existing.company_name = row.name
            existing.symbol = row.symbol
            existing.series = row.series
            existing.source_updated_at = _now()
            summary.entities_updated += 1
        else:
            summary.entities_unchanged += 1
            if current_alias is None:
                # Entity exists (e.g. seeded by an earlier partial run)
                # but is missing its current-symbol alias — heal it rather
                # than leaving the entity unreachable by symbol lookup.
                db.add(CompanyAlias(
                    entity_id=existing.entity_id, alias_type="symbol", alias_value=row.symbol,
                    exchange="NSE", valid_from=row.listing_date, valid_to=None, source=source,
                ))
                summary.symbol_aliases_created += 1

    summary.unique_isins = len(seen_isins)
    return summary


async def apply_symbol_change_aliases(
    db: AsyncSession, rows: list[SymbolChangeRow], *, source: str = "nse_symbolchange",
) -> ImportSummary:
    """Only creates an old_symbol alias when new_symbol resolves, via the
    resolver, to exactly one real CompanyEntity that the EQ import already
    created — never a guess, and never a new entity. A rename chain (A->B,
    B->C) resolves both A and B as old_symbol aliases on C's entity_id,
    each windowed to its own real change_date. A row whose new_symbol isn't
    a real, currently-known entity (fund renames, or — a real, confirmed
    case — LTIMindtree's LTIM being absent from a given EQUITY_L.csv
    snapshot even though the rename itself is real and NSE-sourced) is
    skipped and counted, not force-fit."""
    from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus

    summary = ImportSummary()

    # Follows a multi-hop rename chain (TELCO->TATAMOTORS->TMPV) forward to
    # its current terminal symbol, so both TELCO and TATAMOTORS end up as
    # old_symbol aliases on whichever entity TMPV resolves to — not just the
    # immediate predecessor.
    def _walk_forward(symbol: str, _seen: set[str] | None = None) -> str:
        _seen = _seen or set()
        if symbol in _seen:
            return symbol  # cycle guard, shouldn't happen in real data
        _seen.add(symbol)
        # symbol appears as an OLD symbol of some later rename? walk further.
        for r in rows:
            if normalize_identifier(r.old_symbol) == symbol:
                return _walk_forward(normalize_identifier(r.new_symbol), _seen)
        return symbol

    for r in rows:
        terminal_symbol = _walk_forward(normalize_identifier(r.new_symbol))
        result = await resolve_identifier(db, terminal_symbol)
        if result.status != ResolutionStatus.RESOLVED:
            summary.old_symbol_rows_skipped_no_target += 1
            continue
        entity_id = result.entity_id

        existing = (await db.execute(
            select(CompanyAlias).where(
                CompanyAlias.entity_id == entity_id,
                CompanyAlias.alias_type == "old_symbol",
                CompanyAlias.alias_value == normalize_identifier(r.old_symbol),
            )
        )).scalars().first()
        if existing is not None:
            summary.entities_unchanged += 1
            continue

        db.add(CompanyAlias(
            entity_id=entity_id, alias_type="old_symbol", alias_value=normalize_identifier(r.old_symbol),
            exchange="NSE", valid_from=None, valid_to=r.change_date, source=source,
        ))
        summary.old_symbol_aliases_created += 1

    return summary


# Real, individually-verified vendor/provider ticker variants — found and
# checked against the live NSE EQ file during the C1 reconciliation (see
# artifacts/company_identity_c1_reconciliation.md §3b). These are NOT NSE
# renames (they don't appear in symbolchange.csv — they were never the
# official symbol), so they can't be derived from either real source file
# automatically; each one here was individually confirmed, not
# fuzzy-matched. New entries should only be added the same way: a real,
# checked match against a live NSE source, never a string-similarity guess.
KNOWN_PROVIDER_SYMBOL_ALIASES: tuple[tuple[str, str], ...] = (
    ("CEAT", "CEATLTD"),           # graph ticker -> real NSE symbol
    ("HPCL", "HINDPETRO"),
    ("IOCL", "IOC"),
    ("AUROBINDOPHARMA", "AUROPHARMA"),
)


async def apply_known_provider_aliases(
    db: AsyncSession, pairs: tuple[tuple[str, str], ...] = KNOWN_PROVIDER_SYMBOL_ALIASES,
    *, source: str = "verified_provider_mapping",
) -> ImportSummary:
    """Attaches a provider_symbol alias only when the REAL symbol side
    already resolves to an entity the EQ import created — same
    never-guess, never-create discipline as apply_symbol_change_aliases()."""
    from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus

    summary = ImportSummary()
    for provider_symbol, real_symbol in pairs:
        result = await resolve_identifier(db, real_symbol)
        if result.status != ResolutionStatus.RESOLVED:
            summary.old_symbol_rows_skipped_no_target += 1
            continue
        existing = (await db.execute(
            select(CompanyAlias).where(
                CompanyAlias.entity_id == result.entity_id,
                CompanyAlias.alias_type == "provider_symbol",
                CompanyAlias.alias_value == normalize_identifier(provider_symbol),
            )
        )).scalars().first()
        if existing is not None:
            summary.entities_unchanged += 1
            continue
        db.add(CompanyAlias(
            entity_id=result.entity_id, alias_type="provider_symbol",
            alias_value=normalize_identifier(provider_symbol), exchange="NSE",
            valid_from=None, valid_to=None, source=source,
        ))
        summary.old_symbol_aliases_created += 1
    return summary


async def run_full_import(
    db: AsyncSession, eq_csv_text: str, symbolchange_csv_text: str | None = None,
    *, allowed_series: set[str] | None = None,
) -> dict[str, Any]:
    """The orchestrator: EQ import first (creates entities + current
    symbol aliases), then symbol-change aliases (only ever attaches to
    what the EQ import just created). Returns the
    '2,296 NSE EQ rows -> X canonical entities -> X unique ISINs -> aliases
    -> unresolved/conflicts' shape — nothing silently dropped."""
    eq_rows = parse_nse_eq_csv(eq_csv_text)
    eq_summary = await upsert_company_entities(db, eq_rows, allowed_series=allowed_series)

    change_summary = ImportSummary()
    if symbolchange_csv_text:
        change_rows = parse_nse_symbolchange_csv(symbolchange_csv_text)
        change_summary = await apply_symbol_change_aliases(db, change_rows)

    provider_summary = await apply_known_provider_aliases(db)

    total_entities = (await db.execute(select(CompanyEntity))).scalars().all()

    return {
        "eq_import": eq_summary.as_dict(),
        "symbol_change_import": change_summary.as_dict(),
        "provider_alias_import": provider_summary.as_dict(),
        "total_canonical_entities_in_db": len(total_entities),
        "total_unique_isins_in_db": len({e.isin for e in total_entities if e.isin}),
    }

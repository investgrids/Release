"""
Ingest orchestrator — S3-B. Fetches real NSE filings for one symbol, parses
real XBRL, writes FinancialFact rows with real provenance, quality-checks
against the symbol's own real trailing DB history. Upserts on the real
identity index (symbol, metric_code, fiscal_year, fiscal_quarter,
period_type, consolidation_scope) — re-running this for the same real
filing never duplicates rows.

Deliberately NOT wired into any scheduler or API route yet — a manual,
inspectable function for S3-C's backfill, same phase-lock discipline as
the rest of this initiative (engine.py's own MarketRippleScore.publishable
stays False regardless of what this ingests).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.financial_fact import (
    EXTRACTION_PARSE_FAILED,
    EXTRACTION_POPULATED,
    EXTRACTION_SOURCE_UNAVAILABLE,
    EXTRACTION_TAG_MISSING,
    FinancialFact,
)
from app.services.financial_facts import nse_xbrl_client as client
from app.services.financial_facts import quality
from app.services.financial_facts.metrics import ANNUAL_METRICS, QUARTERLY_METRICS, MetricDef

_QUARTER_MAP = {"First Quarter": 1, "Second Quarter": 2, "Third Quarter": 3, "Fourth Quarter": 4}


def _fiscal_year_from_financial_year(raw: str | None) -> int | None:
    """Real field format confirmed live: "01-Apr-2024 To 31-Mar-2025" ->
    Indian FY convention names it by the END year (FY25)."""
    if not raw:
        return None
    m = re.search(r"(\d{4})\s*$", raw.strip())
    return int(m.group(1)) if m else None


async def _trailing_values(db: AsyncSession, symbol: str, metric_code: str, scope: str, before_fy: int, before_fq: int | None) -> list[float]:
    """Real prior POPULATED values for this exact (symbol, metric, scope),
    most-recent-first, strictly before the period being ingested — never
    includes the value currently being assessed."""
    rows = (await db.execute(
        select(FinancialFact.value, FinancialFact.fiscal_year, FinancialFact.fiscal_quarter)
        .where(
            FinancialFact.symbol == symbol, FinancialFact.metric_code == metric_code,
            FinancialFact.consolidation_scope == scope, FinancialFact.extraction_status == EXTRACTION_POPULATED,
        )
    )).all()
    ordered = sorted(rows, key=lambda r: (r[1], r[2] or 0), reverse=True)
    fq_key = before_fq or 0
    return [v for v, fy, fq in ordered if (fy, fq or 0) < (before_fy, fq_key) and v is not None]


async def _upsert(db: AsyncSession, **kwargs) -> None:
    existing = (await db.execute(
        select(FinancialFact).where(
            FinancialFact.symbol == kwargs["symbol"], FinancialFact.metric_code == kwargs["metric_code"],
            FinancialFact.fiscal_year == kwargs["fiscal_year"], FinancialFact.fiscal_quarter == kwargs.get("fiscal_quarter"),
            FinancialFact.period_type == kwargs["period_type"], FinancialFact.consolidation_scope == kwargs["consolidation_scope"],
        )
    )).scalar_one_or_none()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
    else:
        db.add(FinancialFact(**kwargs))


async def ingest_period(db: AsyncSession, symbol: str, period_type: str, real_quarters: int = 4) -> dict:
    """Ingests the last `real_quarters` real Non-Consolidated filings of
    `period_type` ("Quarterly" | "Annual") for `symbol`. Returns real
    per-status counts, never a fabricated "success" summary."""
    symbol = symbol.upper()
    metric_defs = QUARTERLY_METRICS if period_type == "Quarterly" else ANNUAL_METRICS
    counts = {"populated": 0, "tag_missing": 0, "source_unavailable": 0, "parse_failed": 0, "anomaly": 0, "implausible_scale": 0}

    session = client._session()
    try:
        rows = client.fetch_financial_results(symbol, period_type, session=session)
    except Exception:
        return {"error": "fetch_financial_results failed", **counts}
    # Real bug found live while validating this module: filings come back
    # newest-first (client.fetch_financial_results' own real sort order).
    # Processing them in that order means the OLDEST requested quarter is
    # ingested LAST, so anomaly detection for it sees zero real trailing
    # context (the chronologically-prior quarters it needs haven't been
    # written yet) and trivially reports OK — exactly what happened on the
    # first real run (0 anomalies found despite the known real ICICIBANK
    # Q1 FY25 case). Fetch a few extra real quarters as trailing buffer,
    # then process strictly oldest-first so each period's own real prior
    # quarters are already in the DB by the time it's assessed.
    buffer = 4
    real_filings = list(reversed(client.non_consolidated_with_real_xbrl(rows)[: real_quarters + buffer]))

    for filing in real_filings:
        fiscal_year = _fiscal_year_from_financial_year(filing.get("financialYear"))
        fiscal_quarter = _QUARTER_MAP.get(filing.get("relatingTo")) if period_type == "Quarterly" else None
        if fiscal_year is None:
            continue
        published_at = filing.get("_broadcast_dt")
        xbrl_url = filing["xbrl"]

        try:
            xbrl_content = client.fetch_xbrl_text(xbrl_url, session=session)
            fetch_ok = True
        except Exception:
            xbrl_content = ""
            fetch_ok = False

        for m in metric_defs:
            common = dict(
                symbol=symbol, metric_code=m.code, metric_name=m.name, unit=m.unit,
                fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter, period_type=period_type,
                consolidation_scope="Non-Consolidated", source_provider="NSE",
                source_document_url=xbrl_url, source_document_id=str(filing.get("seqNumber") or ""),
                taxonomy="banking_entry_point_2019-09-30", published_at=published_at,
                observed_at=datetime.now(timezone.utc),
            )

            if m.tag is None:
                # Confirmed structurally absent from this real taxonomy —
                # an explicit, named gap (rule 3), tied to the real filing
                # we actually checked (source_document_url/id still real).
                await _upsert(db, **common, value=None, source_tag=None,
                               extraction_status=EXTRACTION_SOURCE_UNAVAILABLE, quality_status=None, quality_reason=None)
                counts["source_unavailable"] += 1
                continue

            if not fetch_ok:
                await _upsert(db, **common, value=None, source_tag=f"in-bse-fin:{m.tag}",
                               extraction_status=EXTRACTION_PARSE_FAILED, quality_status=None, quality_reason=None)
                counts["parse_failed"] += 1
                continue

            value = client.extract_tag_value(xbrl_content, m.tag)
            if value is None:
                await _upsert(db, **common, value=None, source_tag=f"in-bse-fin:{m.tag}",
                               extraction_status=EXTRACTION_TAG_MISSING, quality_status=None, quality_reason=None)
                counts["tag_missing"] += 1
                continue

            trailing = await _trailing_values(db, symbol, m.code, "Non-Consolidated", fiscal_year, fiscal_quarter)
            quality_status, quality_reason = quality.assess(value, trailing)
            # S4.5: cross-sectional/metric plausibility check runs in
            # addition to the within-entity check above, not instead of it
            # — a value already flagged ANOMALY stays ANOMALY (it's already
            # excluded from scoring; no need to also evaluate plausibility).
            if quality_status == "OK":
                quality_status, quality_reason = quality.assess_plausibility(m.code, value)
            await _upsert(db, **common, value=value, source_tag=f"in-bse-fin:{m.tag}",
                           extraction_status=EXTRACTION_POPULATED, quality_status=quality_status, quality_reason=quality_reason)
            counts["populated"] += 1
            if quality_status == "ANOMALY":
                counts["anomaly"] += 1
            elif quality_status == "IMPLAUSIBLE_SCALE":
                counts["implausible_scale"] += 1

    await db.commit()
    return counts

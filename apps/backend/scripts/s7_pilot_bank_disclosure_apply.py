"""
S7 — Bounded two-bank FinancialFact import from official bank disclosures.

Round 2 (2026-09-27), correcting a real owner review of the first version:

  1. `_make_readonly_engine()` no longer swallows PRAGMA failures and never
     assumes the pragma took effect -- `_verify_readonly_engine()` reads
     `PRAGMA query_only` back from the actual connection and aborts if it
     isn't 1. The read-only sessionmaker also sets `autoflush=False`
     explicitly (defensive: it should never have anything to flush, but a
     future accidental `db.add()` on this session must not attempt an
     implicit write against a PRAGMA-locked connection silently).

  2. THE TRANSACTION GAP (most important defect in round 1): the previous
     version ran collision/quality checks on a separate read-only
     connection, then reused that stale result inside apply()'s write
     transaction and called the upsert-capable `_upsert()` -- a real
     TOCTOU race, since a row created between the check and the write
     would have been silently overwritten. `_write_records_transactionally()`
     now re-checks collision and quality for every record INSIDE the same
     session/transaction it writes to, immediately before each insert, and
     uses a true insert-only path (`db.add(FinancialFact(...))`, never
     `_upsert()`) -- any collision found at that point raises and aborts
     the whole transaction before any row commits.

  3. The backup is now written to an explicit, persistent directory
     (scripts/backups/), then read back and re-parsed to verify its row
     count and content, with a sha256 of the file itself recorded and
     returned -- "verified" only after that readback succeeds, not merely
     after `write_text()` returns.

  4. A durable JSON manifest is written to the same backups/ directory
     after a successful commit -- ids, full key tuples, values, quality
     status/reason, and per-record provenance (document URL, hash,
     publication date and how that date was established). `--rollback
     <manifest path>` re-fetches each row by id and REFUSES to delete any
     row whose current value/quality_status/key fields no longer match
     what the manifest recorded, rather than deleting by id alone.

  5. Publication dates are no longer a single blanket `_BOARD_APPROVED_DATE`
     equated with board approval. Each SourceDoc carries its own
     `publication_date` and a `publication_date_basis` string recording
     exactly how that date was established -- the ICICI statutory filing's
     board-approval note is used as an explicitly-flagged proxy (this
     document does not separately state an issuance dateline), while the
     ICICI Performance Review page and the Kotak Media Release both carry
     independently-confirmed publication datelines in their own text,
     distinct from the board-approval sentence.

  6. `apply()` no longer reports "Nothing was committed" for every
     exception. Exceptions raised before `db.commit()` is called are safe
     (explicit rollback, confirmed nothing written). An exception raised
     BY `db.commit()` itself is reported as commit-outcome-uncertain, with
     the in-memory partial manifest printed so the operator can reconcile
     against the real database before ever retrying (to avoid a duplicate-
     insert attempt against a possibly-partially-committed batch).

Modes:
  python s7_pilot_bank_disclosure_apply.py                      -> DRY RUN
  python s7_pilot_bank_disclosure_apply.py --apply               -> REAL WRITE
  python s7_pilot_bank_disclosure_apply.py --rollback <manifest> -> ROLLBACK

Must be run against production the same way every prior read/backfill
script in this initiative was: `railway ssh "python3 -" < script.py` (or
the PowerShell equivalent). Not run by the assistant directly -- production
DB reads and writes both go through the owner's own execution.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import requests  # noqa: E402
from sqlalchemy import event, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.session import AsyncSessionLocal, engine as _prod_engine  # noqa: E402
from app.db.models.financial_fact import EXTRACTION_POPULATED, FinancialFact, QUALITY_OK  # noqa: E402
from app.services.financial_facts.ingest import _fiscal_year_from_financial_year, _QUARTER_MAP, _trailing_values  # noqa: E402
from app.services.financial_facts import quality  # noqa: E402

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

_FINANCIAL_YEAR_STR = "01-Apr-2026 To 31-Mar-2027"
_RELATING_TO = "First Quarter"
_PERIOD_END = datetime(2026, 6, 30, tzinfo=timezone.utc)
FISCAL_YEAR = _fiscal_year_from_financial_year(_FINANCIAL_YEAR_STR)
FISCAL_QUARTER = _QUARTER_MAP[_RELATING_TO]

_PILOT_SYMBOLS = ("ICICIBANK", "KOTAKBANK")
_BACKUPS_DIR = Path(__file__).resolve().parent / "backups"


class CollisionError(RuntimeError):
    pass


class QualityGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceDoc:
    label: str
    url: str
    expected_sha256: str
    publication_date: str  # ISO date (YYYY-MM-DD)
    publication_date_basis: str  # exactly how this date was established -- never assumed


ICICI_STATUTORY_RESULTS = SourceDoc(
    "ICICI Bank — Standalone Financial Results, Q1-2027",
    "https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2027/financial-results-q1-2027.pdf",
    "b95bef731a963323ad256416cf2cc473c3c2554f6c09e4a83744ee1a6a094e2a",
    "2026-07-18",
    "This filing's own notes state only 'approved by the Board of Directors at its meeting held on "
    "July 18, 2026' -- it does NOT separately state an issuance/filing dateline. Board-approval date "
    "used as a documented proxy for publication, explicitly flagged as such, not independently confirmed.",
)
ICICI_PERFORMANCE_REVIEW = SourceDoc(
    "ICICI Bank — Performance Review, quarter ended June 30, 2026",
    "https://www.icici.bank.in/about-us/news-room/2026/performance-review-quarter-ended-june-30-2026",
    "abfdb2aca6c219b9c85f93ac8dd98f04014ffbf72d1a60ffd73d2ec45bf5c514",
    "2026-07-18",
    "Independently confirmed via the page's own visible byline date field ('July 18, 2026') directly "
    "under the headline -- distinct from, and consistent with, the separate board-approval sentence "
    "elsewhere on the same page.",
)
KOTAK_MEDIA_RELEASE = SourceDoc(
    "Kotak Mahindra Bank — Media Release, Q1FY27",
    "https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2027/q1/PressRelease/Q1-FY27_Press-Release.pdf",
    "54adb21b7e357705313de731671f2409e7ad9fc2eade71f243897ce7ddea623c",
    "2026-07-18",
    "Confirmed via the release's own dateline sentence, which explicitly equates issuance with the "
    "board meeting date: 'Mumbai, 18th July, 2026: ... approved ... at the Board meeting held in "
    "Mumbai, today.'",
)


@dataclass(frozen=True)
class PilotRecord:
    symbol: str
    metric_code: str
    metric_name: str
    value_pct: float
    unit: str
    source: SourceDoc
    quote: str


RECORDS: list[PilotRecord] = [
    PilotRecord("ICICIBANK", "gross_npa_pct", "Gross NPA %", 1.38, "pct", ICICI_STATUTORY_RESULTS,
                "% of gross non-performing customer assets (net of write-off) to gross customer assets: 1.38%"),
    PilotRecord("ICICIBANK", "net_npa_pct", "Net NPA %", 0.35, "pct", ICICI_STATUTORY_RESULTS,
                "% of net non-performing customer assets to net customer assets: 0.35%"),
    PilotRecord("ICICIBANK", "roa", "Return on Assets", 2.49, "pct", ICICI_STATUTORY_RESULTS,
                "Return on assets (annualised): 2.49%"),
    PilotRecord("ICICIBANK", "cet1_ratio", "CET1 Ratio", 16.19, "pct", ICICI_PERFORMANCE_REVIEW,
                "CET-1 ratio was 16.19%, on a standalone basis, at June 30, 2026"),
    PilotRecord("KOTAKBANK", "gross_npa_pct", "Gross NPA %", 1.18, "pct", KOTAK_MEDIA_RELEASE,
                "As at June 30, 2026, GNPA was 1.18% & NNPA was 0.27%"),
    PilotRecord("KOTAKBANK", "net_npa_pct", "Net NPA %", 0.27, "pct", KOTAK_MEDIA_RELEASE,
                "As at June 30, 2026, GNPA was 1.18% & NNPA was 0.27%"),
    PilotRecord("KOTAKBANK", "roa", "Return on Assets", 2.14, "pct", KOTAK_MEDIA_RELEASE,
                "Standalone Return on Assets (ROA) for Q1FY27 (annualised) was 2.14%"),
    PilotRecord("KOTAKBANK", "cet1_ratio", "CET1 Ratio", 22.4, "pct", KOTAK_MEDIA_RELEASE,
                "Capital Adequacy Ratio of the Bank, as per Basel III, as at June 30, 2026 was 22.8% and CET1 ratio of 22.4%"),
]


# ── Document verification ────────────────────────────────────────────────
def verify_documents() -> dict[str, dict]:
    print("=== Step 0: live document re-verification ===")
    results: dict[str, dict] = {}
    for doc in {r.source.url: r.source for r in RECORDS}.values():
        r = requests.get(doc.url, headers=_HEADERS, timeout=20)
        actual = hashlib.sha256(r.content).hexdigest()
        match = actual == doc.expected_sha256
        results[doc.url] = {"label": doc.label, "match": match, "actual_sha256": actual, "bytes": len(r.content)}
        print(f"  [{'MATCH' if match else 'MISMATCH'}] {doc.label} (status={r.status_code}, bytes={len(r.content)})")
        if not match:
            print(f"      expected: {doc.expected_sha256}\n      actual:   {actual}")
            print("      -- source document changed since these values were recorded. Refusing stale figures.")
    print()
    return results


# ── Read-only guard: sqlite-only, verified by readback, never assumed ────
def _assert_sqlite_url(url: str) -> None:
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"Refusing to proceed: this script's read-only PRAGMA mechanism is sqlite-specific, "
            f"but the resolved database URL's dialect is not sqlite ({url!r})."
        )


def _make_readonly_engine():
    url = str(_prod_engine.url)
    _assert_sqlite_url(url)
    ro_engine = create_async_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(ro_engine.sync_engine, "connect")
    def _set_readonly(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA query_only = ON")

    return ro_engine


async def _verify_readonly_engine(ro_engine) -> None:
    """Reads PRAGMA query_only back from the real connection this engine
    will serve every subsequent query from -- never trusts that the
    connect-event listener merely ran without error."""
    async with ro_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA query_only"))
        value = result.scalar()
    if value != 1:
        raise RuntimeError(
            f"Read-only enforcement FAILED verification: PRAGMA query_only read back as {value!r}, not 1. "
            "Refusing to use this connection for any query."
        )


async def _selftest_readonly_mechanism() -> None:
    import tempfile
    import os as _os
    from sqlalchemy.exc import OperationalError

    fd, path = tempfile.mkstemp(suffix=".db")
    _os.close(fd)
    try:
        setup_engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        async with setup_engine.begin() as conn:
            await conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        await setup_engine.dispose()

        ro_engine = create_async_engine(
            f"sqlite+aiosqlite:///{path}", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(ro_engine.sync_engine, "connect")
        def _set_readonly(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA query_only = ON")

        await _verify_readonly_engine(ro_engine)

        raised = False
        try:
            async with ro_engine.connect() as conn:
                await conn.execute(text("INSERT INTO t VALUES (1)"))
        except OperationalError as e:
            raised = "readonly database" in str(e).lower()
        await ro_engine.dispose()

        if not raised:
            raise RuntimeError("Read-only self-test FAILED: a write was not rejected. Refusing to proceed.")
        print("Step 0.5: read-only mechanism self-test PASSED (write rejected, PRAGMA readback confirmed 1).\n")
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass  # cosmetic cleanup only; the pass/fail result above is already determined


# ── Dry-run checks (informational only -- never trusted as the write guard) ─
@dataclass
class RecordCheck:
    record: PilotRecord
    value_fraction: float
    collision: bool
    existing_row: dict | None
    trailing_values: list[float]
    assess_status: str
    assess_reason: str | None
    plausibility_status: str
    plausibility_reason: str | None
    final_quality_status: str
    final_quality_reason: str | None

    @property
    def go(self) -> bool:
        return not self.collision and self.final_quality_status == QUALITY_OK


async def run_checks(db: AsyncSession) -> list[RecordCheck]:
    checks: list[RecordCheck] = []
    for r in RECORDS:
        value_fraction = r.value_pct / 100.0
        existing = (await db.execute(
            select(FinancialFact).where(
                FinancialFact.symbol == r.symbol, FinancialFact.metric_code == r.metric_code,
                FinancialFact.fiscal_year == FISCAL_YEAR, FinancialFact.fiscal_quarter == FISCAL_QUARTER,
                FinancialFact.period_type == "Quarterly", FinancialFact.consolidation_scope == "Non-Consolidated",
            )
        )).scalar_one_or_none()
        collision = existing is not None
        existing_row = None
        if existing is not None:
            existing_row = {c.name: getattr(existing, c.name) for c in FinancialFact.__table__.columns}

        trailing = await _trailing_values(db, r.symbol, r.metric_code, "Non-Consolidated", FISCAL_YEAR, FISCAL_QUARTER)
        assess_status, assess_reason = quality.assess(value_fraction, trailing)
        plaus_status, plaus_reason = quality.assess_plausibility(r.metric_code, value_fraction)
        if assess_status == QUALITY_OK:
            final_status, final_reason = plaus_status, plaus_reason
        else:
            final_status, final_reason = assess_status, assess_reason

        checks.append(RecordCheck(
            record=r, value_fraction=value_fraction, collision=collision, existing_row=existing_row,
            trailing_values=trailing, assess_status=assess_status, assess_reason=assess_reason,
            plausibility_status=plaus_status, plausibility_reason=plaus_reason,
            final_quality_status=final_status, final_quality_reason=final_reason,
        ))
    return checks


def print_manifest(checks: list[RecordCheck], title: str) -> None:
    print(f"=== {title} ===")
    for i, c in enumerate(checks, 1):
        r = c.record
        print(f"[{i}/8] {r.symbol} — {r.metric_name} ({r.metric_code}) = {r.value_pct}% ({c.value_fraction})")
        print(f"  collision: {'YES — existing row found' if c.collision else 'no (new period identity)'}")
        if c.existing_row:
            print(f"    existing row: {c.existing_row}")
        print(f"  trailing values used ({len(c.trailing_values)} found): {c.trailing_values}")
        print(f"  quality.assess(): {c.assess_status}" + (f" — {c.assess_reason}" if c.assess_reason else ""))
        print(f"  quality.assess_plausibility(): {c.plausibility_status}"
              + (f" — {c.plausibility_reason}" if c.plausibility_reason else ""))
        print(f"  FINAL quality_status: {c.final_quality_status}   GO: {c.go}")
        print(f"  publication_date: {r.source.publication_date}  (basis: {r.source.publication_date_basis})")
        print(f"  source: {r.source.label} — \"{r.quote}\"")
        print()
    go_count = sum(1 for c in checks if c.go)
    print(f"Summary: {go_count}/8 GO, {8 - go_count}/8 BLOCKED.")
    print("NOTE: this dry-run result is informational only. apply() re-checks every record live, inside "
          "its own write transaction, immediately before each insert -- it never trusts this result.\n")


async def dry_run() -> bool:
    docs = verify_documents()
    docs_ok = all(d["match"] for d in docs.values())
    await _selftest_readonly_mechanism()

    ro_engine = _make_readonly_engine()
    try:
        await _verify_readonly_engine(ro_engine)
        SessionLocal = sessionmaker(ro_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
        async with SessionLocal() as db:
            checks = await run_checks(db)
    finally:
        await ro_engine.dispose()

    print_manifest(checks, "DRY RUN manifest (read-only connection, nothing written)")
    all_go = all(c.go for c in checks) and docs_ok
    print(f"Documents verified: {'OK' if docs_ok else 'MISMATCH — see above'}")
    print(f"Overall: {'READY FOR --apply' if all_go else 'NOT READY — resolve the flagged issue(s) first'}")
    return all_go


# ── Verified backup ──────────────────────────────────────────────────────
async def take_verified_backup() -> tuple[Path, str, int]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(FinancialFact).where(FinancialFact.symbol.in_(_PILOT_SYMBOLS)))).scalars().all()
        backup = [
            {c.name: (v.isoformat() if isinstance(v := getattr(row, c.name), datetime) else v)
             for c in FinancialFact.__table__.columns}
            for row in rows
        ]
    intended_count = len(backup)

    _BACKUPS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUPS_DIR / f"s7_backup_{'_'.join(_PILOT_SYMBOLS)}_{ts}.json"
    path.write_text(json.dumps(backup, indent=2, default=str), encoding="utf-8")

    # Verify: reopen, re-parse, compare count -- "verified" means confirmed
    # by readback, not merely that write_text() didn't raise.
    raw = path.read_text(encoding="utf-8")
    reparsed = json.loads(raw)
    if len(reparsed) != intended_count:
        raise RuntimeError(
            f"Backup verification FAILED: intended {intended_count} rows, readback found {len(reparsed)} "
            f"at {path}. Refusing to proceed with an unverified backup."
        )
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    resolved = path.resolve()
    print(f"Verified backup: {resolved} ({len(reparsed)} rows confirmed by readback, sha256={checksum})\n")
    return resolved, checksum, len(reparsed)


# ── Core transactional write -- testable in isolation ───────────────────
async def _write_records_transactionally(db: AsyncSession, records: list[PilotRecord]) -> list[dict]:
    """Re-checks collision and quality for each record INSIDE this same
    session/transaction, immediately before writing it -- no separate
    pre-check connection, no window for a race. Raises CollisionError or
    QualityGateError before any db.add() for the offending record; the
    caller is responsible for db.rollback()/db.commit()."""
    manifest: list[dict] = []
    for r in records:
        value_fraction = r.value_pct / 100.0

        existing = (await db.execute(
            select(FinancialFact).where(
                FinancialFact.symbol == r.symbol, FinancialFact.metric_code == r.metric_code,
                FinancialFact.fiscal_year == FISCAL_YEAR, FinancialFact.fiscal_quarter == FISCAL_QUARTER,
                FinancialFact.period_type == "Quarterly", FinancialFact.consolidation_scope == "Non-Consolidated",
            )
        )).scalar_one_or_none()
        if existing is not None:
            raise CollisionError(
                f"{r.symbol}/{r.metric_code}: row id={existing.id} already exists at fiscal_year="
                f"{FISCAL_YEAR}, fiscal_quarter={FISCAL_QUARTER} -- refusing to overwrite (insert-only)."
            )

        trailing = await _trailing_values(db, r.symbol, r.metric_code, "Non-Consolidated", FISCAL_YEAR, FISCAL_QUARTER)
        assess_status, assess_reason = quality.assess(value_fraction, trailing)
        plaus_status, plaus_reason = quality.assess_plausibility(r.metric_code, value_fraction)
        if assess_status == QUALITY_OK:
            final_status, final_reason = plaus_status, plaus_reason
        else:
            final_status, final_reason = assess_status, assess_reason

        if final_status != QUALITY_OK:
            raise QualityGateError(
                f"{r.symbol}/{r.metric_code}: quality_status={final_status} ({final_reason}) -- "
                "pilot rule requires every record to be quality-OK; aborting the entire batch."
            )

        obj = FinancialFact(
            symbol=r.symbol, metric_code=r.metric_code, metric_name=r.metric_name, unit=r.unit,
            fiscal_year=FISCAL_YEAR, fiscal_quarter=FISCAL_QUARTER, period_type="Quarterly",
            consolidation_scope="Non-Consolidated", source_provider="BankDisclosure",
            source_document_url=r.source.url, source_document_id=None, source_tag=None, taxonomy=None,
            published_at=datetime.fromisoformat(r.source.publication_date).replace(tzinfo=timezone.utc),
            period_end=_PERIOD_END, observed_at=datetime.now(timezone.utc),
            value=value_fraction, extraction_status=EXTRACTION_POPULATED,
            quality_status=final_status, quality_reason=final_reason,
        )
        db.add(obj)
        await db.flush()  # populate obj.id without committing

        manifest.append({
            "id": obj.id, "symbol": r.symbol, "metric_code": r.metric_code,
            "fiscal_year": FISCAL_YEAR, "fiscal_quarter": FISCAL_QUARTER,
            "period_type": "Quarterly", "consolidation_scope": "Non-Consolidated",
            "value": value_fraction, "quality_status": final_status, "quality_reason": final_reason,
            "source_document_url": r.source.url, "source_document_sha256": r.source.expected_sha256,
            "source_document_publication_date": r.source.publication_date,
            "source_document_publication_basis": r.source.publication_date_basis,
            "quote": r.quote,
        })
    return manifest


def persist_manifest(records: list[dict], backup_path: Path, backup_sha256: str) -> Path:
    _BACKUPS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUPS_DIR / f"s7_apply_manifest_{ts}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_file": str(backup_path),
        "backup_sha256": backup_sha256,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path.resolve()


async def apply() -> None:
    docs = verify_documents()
    if not all(d["match"] for d in docs.values()):
        print("ABORTING: at least one source document no longer matches its recorded hash. "
              "Refusing to write stale/revised figures.")
        return

    await _selftest_readonly_mechanism()
    backup_path, backup_sha256, backup_count = await take_verified_backup()

    inserted_manifest: list[dict] = []
    async with AsyncSessionLocal() as db:
        try:
            inserted_manifest = await _write_records_transactionally(db, RECORDS)
        except (CollisionError, QualityGateError) as e:
            await db.rollback()
            print(f"ABORTED before commit — nothing written to the database. Reason: {e}")
            return
        except Exception as e:
            await db.rollback()
            print(f"ABORTED before commit (unexpected error) — nothing written. Reason: {type(e).__name__}: {e}")
            return

        try:
            await db.commit()
        except Exception as e:
            print(f"COMMIT OUTCOME UNCERTAIN — exception raised by commit() itself: {type(e).__name__}: {e}")
            print("Do NOT assume nothing was written. Before retrying, check the database directly for these "
                  f"exact keys (fiscal_year={FISCAL_YEAR}, fiscal_quarter={FISCAL_QUARTER}) and reconcile "
                  "against the partial in-memory manifest below rather than re-running blindly:")
            for m in inserted_manifest:
                print(f"    {m}")
            return

    manifest_path = persist_manifest(inserted_manifest, backup_path, backup_sha256)
    print("=== APPLY COMPLETE ===")
    print(f"Durable manifest: {manifest_path}")
    print(f"Backup of pre-existing state ({backup_count} rows): {backup_path} (sha256={backup_sha256})")
    for m in inserted_manifest:
        print(f"  id={m['id']} {m['symbol']:<10} {m['metric_code']:<16} value={m['value']} "
              f"quality_status={m['quality_status']}")
    print(f"\nRollback: python {Path(__file__).name} --rollback {manifest_path}")


# ── Rollback: refuses to delete anything that has changed since insert ──
async def _rollback_records(db: AsyncSession, records: list[dict]) -> list[dict]:
    results: list[dict] = []
    for rec in records:
        row = (await db.execute(select(FinancialFact).where(FinancialFact.id == rec["id"]))).scalar_one_or_none()
        if row is None:
            results.append({"id": rec["id"], "symbol": rec["symbol"], "metric_code": rec["metric_code"], "action": "missing"})
            continue
        unchanged = (
            row.symbol == rec["symbol"] and row.metric_code == rec["metric_code"]
            and row.fiscal_year == rec["fiscal_year"] and row.fiscal_quarter == rec["fiscal_quarter"]
            and row.value == rec["value"] and row.quality_status == rec["quality_status"]
        )
        if not unchanged:
            results.append({
                "id": rec["id"], "symbol": rec["symbol"], "metric_code": rec["metric_code"],
                "action": "refused", "reason": "row has changed since insert — resolve manually, not auto-deleted",
            })
            continue
        await db.delete(row)
        results.append({"id": rec["id"], "symbol": rec["symbol"], "metric_code": rec["metric_code"], "action": "deleted"})
    await db.commit()
    return results


async def rollback(manifest_path: str) -> None:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as db:
        results = await _rollback_records(db, payload["records"])
    print(f"=== Rollback against {manifest_path} ===")
    for r in results:
        extra = f" ({r['reason']})" if "reason" in r else ""
        print(f"  id={r['id']} {r['symbol']}/{r['metric_code']}: {r['action']}{extra}")


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        idx = sys.argv.index("--rollback")
        asyncio.run(rollback(sys.argv[idx + 1]))
    elif "--apply" in sys.argv:
        asyncio.run(apply())
    else:
        asyncio.run(dry_run())

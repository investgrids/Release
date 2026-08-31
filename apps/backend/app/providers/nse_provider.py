"""NSE corporate announcement provider."""
from __future__ import annotations

import hashlib
from datetime import date, datetime

import httpx
import structlog

from .base import BaseProvider, RawItem

log = structlog.get_logger(__name__)

_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"
# Data track Stage 4 (2026-08-07): widens NSE feed scope beyond
# corporate-announcements-only. Confirmed live: corporate-board-meetings
# is a distinct, working, real-content endpoint (not the much larger
# event-calendar endpoint, which is a *future*-scheduled meeting calendar
# with different semantics — 795 distinct symbols but no real "what
# happened" content, flagged as a separate follow-up rather than forced
# into this event-shaped feed). corporates-corporateActions and
# corporates-financial-results were probed live and returned empty
# without a symbol-scoped query at the time — not pursued that pass.
_BOARD_MEETINGS_URL = "https://www.nseindia.com/api/corporate-board-meetings?index=equities"
# Data track — NSE survey re-probe (2026-08-09): corporates-corporateActions
# now confirmed live, bulk, no symbol needed (returns real dividend/split/
# bonus records — a genuinely new content type nothing else here covers).
# corporates-financial-results was re-checked at the same time and is still
# empty in bulk even with a date range — that one still needs a per-symbol
# fan-out to return anything, not pursued.
_CORPORATE_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}
# NSE's own field naming is misleading: `desc` (and `subject`) is a short
# announcement *category* label ("General Updates", "Press Release",
# "Others"), not a headline — confirmed against live API data 2026-08-07.
# `attchmntText` holds the real, substantive sentence and is what should
# become the headline/title; `desc`/`subject` is kept only as a fallback
# for the rare item where attchmntText is empty.
_MAX_HEADLINE_LEN = 180


def _clip_headline(source_text: str) -> str:
    headline = source_text[:_MAX_HEADLINE_LEN]
    if len(source_text) > _MAX_HEADLINE_LEN:
        headline = headline.rsplit(" ", 1)[0].rstrip(",.;") + "…"
    return headline


class NSEProvider(BaseProvider):
    source_name = "NSE"
    capture_raw_evidence = True   # Phase 1B Batch 2, 2026-08-23

    async def _get(self, url: str, params: dict | None = None, feed: str = "unknown") -> list[dict]:
        # Reliability hardening (2026-08-06): confirmed via a direct live test
        # from the actual production (Railway) egress IP that this endpoint
        # currently works fine bare — unlike BSE's, which is actively broken
        # for an unrelated reason (see bse_provider.py's module docstring).
        # Added this warm-up defensively anyway, per a known-reliable
        # community NSE client's documented pattern (github.com/
        # BennyThadikaran/NseIndiaApi): NSE's own site visits the homepage
        # first to pick up session cookies before any /api/* call, and a
        # bare API call with only a static User-Agent is documented there to
        # work intermittently, not reliably. One shared client/cookie-jar
        # for the warm-up + the real call, not two independent connections.
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            await c.get("https://www.nseindia.com/")
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            # NSE Live Ingestion Completeness Audit (owner-authorized 2026-08-30
            # evening) -- observability only, no behavior change. Logs the REAL
            # raw count NSE returned for this sub-feed before the existing
            # [:50] slice below, so a real production incident (raw > 50,
            # meaning real disclosures are being silently dropped today) can
            # be distinguished from harmless combined-feed totals (three
            # independently-capped feeds summing past 50 loses nothing). Does
            # NOT log the URL/query string or response payload.
            raw_count = len(items)
            returned = items[:50]
            log.info(
                "nse_provider.fetch_completeness",
                feed=feed, raw_count=raw_count, returned_count=len(returned),
                truncated=raw_count > 50,
            )
            return returned

    async def fetch_latest(self) -> list[dict]:
        announcements = await self._get(_URL, feed="announcements")
        try:
            board_meetings = await self._get(_BOARD_MEETINGS_URL, feed="board_meetings")
        except Exception:
            # Widened scope is additive — a failure here must not take down
            # the existing, reliability-hardened announcements feed.
            board_meetings = []
        for item in board_meetings:
            item["_kind"] = "board_meeting"
        try:
            corporate_actions = await self._get(_CORPORATE_ACTIONS_URL, feed="corporate_actions")
        except Exception:
            corporate_actions = []
        for item in corporate_actions:
            item["_kind"] = "corporate_action"
        return announcements + board_meetings + corporate_actions

    async def fetch_by_date(self, target: date) -> list[dict]:
        params = {"from_date": target.isoformat(), "to_date": target.isoformat()}
        return await self._get(_URL, params, feed="announcements_by_date")

    async def fetch_announcements_only(self) -> list[RawItem]:
        """Phase 5E.2: the base corporate-announcements sub-feed only
        (no board meetings/corporate actions), fetched and normalized
        through this SAME class — used by company_announcements_service.py
        so it shares this one fetch+normalize path instead of independently
        re-scraping the identical NSE endpoint on its own schedule.

        Root cause this fixes: before this, two unrelated code paths both
        polled `_URL` and each hashed the same real filing into a
        DIFFERENT id namespace (`nse-<hash>` here vs `ann_<hash>_nse` in
        company_announcements_service.py) — so the same NSE announcement
        became an Event/NewsArticle row AND an unrelated-looking
        CompanyAnnouncement row, confirmed live in the dev DB (9 of 20
        CompanyAnnouncement rows had a same-day Event/NewsArticle
        duplicate). Consumers sharing this method's RawItem.id can now
        derive a correlated CompanyAnnouncement id deterministically,
        closing that specific duplicate class without any fuzzy matching."""
        raw = await self._get(_URL, feed="announcements_via_company_service")
        out: list[RawItem] = []
        for r in raw:
            item = self._normalize_announcement(r)
            if item and self.validate(item):
                out.append(item)
        return out

    def normalize(self, raw: dict) -> RawItem | None:
        kind = raw.get("_kind")
        if kind == "board_meeting":
            return self._normalize_board_meeting(raw)
        if kind == "corporate_action":
            return self._normalize_corporate_action(raw)
        return self._normalize_announcement(raw)

    def _normalize_announcement(self, raw: dict) -> RawItem | None:
        category = (raw.get("desc") or raw.get("subject") or "").strip()
        body = (raw.get("attchmntText") or "").strip()
        source_text = body or category
        if not source_text:
            return None
        an_no = raw.get("an_no", "")
        uid = f"nse-{an_no}" if an_no else f"nse-{hashlib.md5(source_text.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=_clip_headline(source_text),
            summary=source_text[:1000],
            source="NSE",
            published_at=(raw.get("sort_date") or "")[:10],
            companies=[raw["symbol"]] if raw.get("symbol") else [],
            # None, not a hardcoded placeholder -- see RawItem's own
            # docstring. The real per-event score comes from the Event
            # Impact Pipeline once enrichment completes.
            impact_score=None,
            event_type="corporate",
            # Carried through so company_announcements_service.py (Phase
            # 5E.2) doesn't need its own independent NSE fetch just to get
            # a human-readable company name — one normalize path, two
            # consumers.
            extra={"company_name": raw.get("comp") or raw.get("companyName") or ""},
        )

    def _normalize_board_meeting(self, raw: dict) -> RawItem | None:
        # Same misleading-field-name pattern as announcements: `bm_purpose`
        # is a short category label ("Financial Results", "Board Meeting
        # Intimation"), `bm_desc` holds the real sentence — confirmed
        # against live API data 2026-08-07.
        source_text = (raw.get("bm_desc") or raw.get("bm_purpose") or "").strip()
        if not source_text:
            return None
        # bm_timestamp is when NSE recorded this intimation (real, past);
        # bm_date is the *future* scheduled meeting date — using bm_date
        # here would backdate/misdate the event, so bm_timestamp is the
        # only correct source for published_at.
        published_at = ""
        ts = raw.get("bm_timestamp")
        if ts:
            try:
                published_at = datetime.strptime(ts, "%d-%b-%Y %H:%M:%S").date().isoformat()
            except ValueError:
                published_at = ""
        symbol = raw.get("bm_symbol", "")
        uid_src = f"{symbol}|{ts}|{source_text}"
        uid = f"nse-bm-{hashlib.md5(uid_src.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=_clip_headline(source_text),
            summary=source_text[:1000],
            source="NSE",
            published_at=published_at,
            companies=[symbol] if symbol else [],
            impact_score=None,  # see RawItem's docstring -- not a real per-event score
            event_type="corporate",
        )

    def _normalize_corporate_action(self, raw: dict) -> RawItem | None:
        # Unlike announcements/board-meetings, `subject` here is already the
        # real, specific sentence ("Interim Dividend - Rs 23 Per Share"), not
        # a generic category label — confirmed against live API data
        # 2026-08-09. No fallback field needed.
        source_text = (raw.get("subject") or "").strip()
        if not source_text:
            return None
        # Same misdating risk already documented for board meetings:
        # exDate/recDate are the *future* effective dates of the action
        # (when it takes effect), not when NSE recorded/broadcast it.
        # caBroadcastDate is the only "when we found out" field, but it's
        # frequently null in practice — left blank rather than guessed at
        # with an effective date, same principle as bm_date above.
        published_at = ""
        broadcast = raw.get("caBroadcastDate")
        if broadcast:
            try:
                published_at = datetime.strptime(broadcast, "%d-%b-%Y %H:%M:%S").date().isoformat()
            except ValueError:
                try:
                    published_at = datetime.strptime(broadcast, "%d-%b-%Y").date().isoformat()
                except ValueError:
                    published_at = ""
        symbol = raw.get("symbol", "")
        ex_date = raw.get("exDate", "")
        uid_src = f"{symbol}|{ex_date}|{source_text}"
        uid = f"nse-ca-{hashlib.md5(uid_src.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=_clip_headline(source_text),
            summary=source_text[:1000],
            source="NSE",
            published_at=published_at,
            companies=[symbol] if symbol else [],
            impact_score=None,  # see RawItem's docstring -- not a real per-event score
            event_type="corporate",
        )

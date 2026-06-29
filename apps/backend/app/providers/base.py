"""
Provider interface — all data source adapters implement this ABC.
Each provider is responsible for:
  - fetching raw data from an external source
  - normalising it to a standard dict schema
  - validating individual records
  - deduplicating against an existing ID set
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class RawItem:
    """Canonical normalised record returned by every provider."""
    __slots__ = (
        "id", "headline", "summary", "source", "url",
        "published_at", "companies", "impact_score",
        "event_type", "ministry", "extra",
    )

    def __init__(
        self,
        id: str,
        headline: str,
        summary: str = "",
        source: str = "",
        url: str = "",
        published_at: str = "",
        companies: list[str] | None = None,
        impact_score: float = 7.0,
        event_type: str = "news",
        ministry: str = "",
        extra: dict | None = None,
    ) -> None:
        self.id           = id
        self.headline     = headline
        self.summary      = summary
        self.source       = source
        self.url          = url
        self.published_at = published_at
        self.companies    = companies or []
        self.impact_score = impact_score
        self.event_type   = event_type
        self.ministry     = ministry
        self.extra        = extra or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":           self.id,
            "headline":     self.headline,
            "summary":      self.summary,
            "source":       self.source,
            "url":          self.url,
            "published_at": self.published_at,
            "companies":    self.companies,
            "impact_score": self.impact_score,
            "event_type":   self.event_type,
            "ministry":     self.ministry,
            **self.extra,
        }


class BaseProvider(ABC):
    """Abstract data-source provider. Implement one per external data source."""

    source_name: str = "unknown"

    # ── Must implement ────────────────────────────────────────────────────────

    @abstractmethod
    async def fetch_latest(self) -> list[dict]:
        """Fetch the most recent items from the source. Returns raw dicts."""

    @abstractmethod
    async def fetch_by_date(self, target: date) -> list[dict]:
        """Fetch items published on a specific date."""

    @abstractmethod
    def normalize(self, raw: dict) -> RawItem | None:
        """
        Convert one raw provider dict to a canonical RawItem.
        Return None to discard the record.
        """

    # ── Provided (override if needed) ─────────────────────────────────────────

    def validate(self, item: RawItem) -> bool:
        """Return False to discard a normalised item."""
        return bool(item.id and item.headline)

    def deduplicate(
        self,
        items: list[RawItem],
        existing_ids: set[str],
    ) -> list[RawItem]:
        """Remove items whose id is already in existing_ids."""
        seen: set[str] = set()
        result: list[RawItem] = []
        for item in items:
            if item.id in existing_ids or item.id in seen:
                continue
            seen.add(item.id)
            result.append(item)
        return result

    async def fetch_and_normalize(self) -> list[RawItem]:
        """Full pipeline: fetch → normalize → validate. Does NOT deduplicate."""
        import structlog
        log = structlog.get_logger(__name__)
        try:
            raw_items = await self.fetch_latest()
        except Exception as exc:
            log.warning("provider.fetch_failed", source=self.source_name, error=str(exc))
            return []

        result: list[RawItem] = []
        for raw in raw_items:
            try:
                item = self.normalize(raw)
                if item and self.validate(item):
                    result.append(item)
            except Exception as exc:
                log.debug("provider.normalize_error", source=self.source_name, error=str(exc))
        log.info("provider.fetched", source=self.source_name, count=len(result))
        return result

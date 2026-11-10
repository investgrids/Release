"""
Workstream C (2026-11-10): mark zero-search-visibility policy_intelligence
articles as noindex (intelligence_articles.search_indexable = False).

Evidence for the slug list (scripts/data/noindex_policy_slugs_2026_11_10.txt):
the 1,523 published policy_intelligence URLs in the 2026-10-24 inventory,
minus the 84 that appear anywhere in the Google Search Console Performance
export for marketripple.in (Web, last 3 months, exported 2026-11-10). The
remaining 1,439 drew no measurable impressions in that window.

Scope guards: only rows that are status='published' AND
article_type='policy_intelligence' AND whose slug is in the list are ever
touched. Content is never modified; the page stays live and linkable.

Dry run by default. Idempotent.

Usage (from apps/backend):
  python scripts/backfill_search_indexable_2026_11_10.py            # dry run
  python scripts/backfill_search_indexable_2026_11_10.py --apply    # write False
  python scripts/backfill_search_indexable_2026_11_10.py --revert   # write True back (rollback)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import select, update  # noqa: E402

from app.db.models.intelligence_article import IntelligenceArticle  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

SLUG_FILE = Path(__file__).parent / "data" / "noindex_policy_slugs_2026_11_10.txt"
ARTICLE_TYPE = "policy_intelligence"


def load_slugs(path: Path = SLUG_FILE) -> list[str]:
    return [s.strip() for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


async def run(slugs: list[str], mode: str) -> dict:
    target = mode == "revert"
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle.slug, IntelligenceArticle.search_indexable)
            .where(IntelligenceArticle.slug.in_(slugs))
            .where(IntelligenceArticle.status == "published")
            .where(IntelligenceArticle.article_type == ARTICLE_TYPE)
        )).all()
        matched = {r.slug: r.search_indexable for r in rows}
        to_change = [s for s, v in matched.items() if bool(v) != target]

        if mode in ("apply", "revert") and to_change:
            await db.execute(
                update(IntelligenceArticle)
                .where(IntelligenceArticle.slug.in_(to_change))
                .where(IntelligenceArticle.status == "published")
                .where(IntelligenceArticle.article_type == ARTICLE_TYPE)
                .values(search_indexable=target)
            )
            await db.commit()

    return {
        "mode": mode,
        "slugs_in_list": len(slugs),
        "matched_published_policy": len(matched),
        "not_found_or_out_of_scope": len(slugs) - len(matched),
        "already_in_target_state": len(matched) - len(to_change),
        "changed" if mode != "dry_run" else "would_change": len(to_change),
    }


def main() -> None:
    args = set(sys.argv[1:])
    if args - {"--apply", "--revert"} or {"--apply", "--revert"} <= args:
        print("usage: backfill_search_indexable_2026_11_10.py [--apply | --revert]", file=sys.stderr)
        sys.exit(2)
    mode = "apply" if "--apply" in args else "revert" if "--revert" in args else "dry_run"
    for k, v in asyncio.run(run(load_slugs(), mode)).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()

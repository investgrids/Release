"""
Regenerates the frontend's real backend-contract fixtures (2026-09-22,
six-mode activation-wiring commit).

apps/web/components/ai/__fixtures__/backend-real/*.json are captured
output of the REAL finalize_v3_response() — the same six scenarios
tests/services/test_aev2_frontend_contract.py exercises — never hand-
authored. They exist so the frontend's own contract tests
(answerTypes.backendContract.test.ts) run against what this backend
actually produces, not a TypeScript developer's belief about its shape.

Run this from apps/backend whenever test_aev2_frontend_contract.py's
scenario builders change, then re-run the frontend contract tests to
confirm they still pass against the refreshed shape:

    python scripts/export_aev2_contract_fixtures.py

Never hand-edit the generated JSON files directly.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.response_finalize import finalize_v3_response

OUT_DIR = Path(__file__).resolve().parents[2] / "web" / "components" / "ai" / "__fixtures__" / "backend-real"


async def _drain() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def _export() -> None:
    from tests.services.test_aev2_frontend_contract import SCENARIOS

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with patch("app.services.ai_search.aev2.mode.AEV2_BUILD_COMPLETE", True), \
         patch("app.services.ai_search.response_finalize.get_aev2_mode", lambda: AEV2Mode.PUBLIC):
        for name, builder in SCENARIOS.items():
            final = finalize_v3_response("contract-test-query", builder(), was_cached=False)
            await _drain()
            out_path = OUT_DIR / f"{name}.json"
            out_path.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {out_path}")


if __name__ == "__main__":
    asyncio.run(_export())

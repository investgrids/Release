# Real backend-contract fixtures

These six JSON files are **captured output of the real backend
finalizer** (`finalize_v3_response`), not hand-authored TypeScript
objects. They exist so `answerTypes.backendContract.test.ts` proves the
frontend's gate functions (`toDirectCompanyResearchAEV2Answer` etc.)
accept what this backend *actually* produces — closing the boundary
risk every other eligibility-contract test file leaves open by testing
only against fixtures that *mirror* the backend's believed shape.

## Regenerating

Run from `apps/backend` whenever
`tests/services/test_aev2_frontend_contract.py`'s scenario builders
change:

```
cd apps/backend
PYTHONPATH=. python scripts/export_aev2_contract_fixtures.py
```

Then re-run `apps/web`'s `answerTypes.backendContract.test.ts` to
confirm it still passes against the refreshed shape.

**Never hand-edit these JSON files directly** — any change should come
from the generator script above, or the fixture stops being a real
backend contract and becomes exactly the kind of mirrored guess this
file set exists to avoid.

Generated with `AEV2_BUILD_COMPLETE=True` and `AI_SEARCH_AEV2_MODE=
public` patched only for the duration of the export script — this does
not reflect production, where both stay off (see `aev2/mode.py`). The
`answer_experience_v2` field these fixtures carry is exactly what a real
response would contain *if* both activation gates were ever opened.

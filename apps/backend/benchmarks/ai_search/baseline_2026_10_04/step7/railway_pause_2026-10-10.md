# Railway pause — 2026-10-10 (owner request: no billing for 10 days)

Stopped (not removed) with `deploymentStop`; resume with `deploymentRestart` on the same deployment IDs. Nothing was deleted: the persistent volume (SQLite DB) and the `ig-backups` bucket are untouched and keep their small storage charge.

| Service | Deployment ID | Image / source | Status before |
|---|---|---|---|
| backend | 29e8ec39-4454-4002-b4a7-89254cc26950 | sha256:5b89ef7fcbd6f… (CLI deploy of 2026-10-04, no commit hash) | SUCCESS |
| Redis | dcd0a8e4-a000-436d-a471-e5ac421d9a58 | Railway Redis (2026-09-05) | SUCCESS |

Project `ig-backend` c5e0c566-6235-44fa-9c3c-581a5804002d, environment production 5570023b-a028-49a1-8f6a-56174b616aba, backend service e7e13992-bff4-49d5-ab50-87b933a8e55a, Redis service 89fea2a3-ecc0-4609-b58e-6d9a06d47e18.

Resume (Redis first, then backend):
  railway api 'mutation { deploymentRestart(id: "dcd0a8e4-a000-436d-a471-e5ac421d9a58") }'
  railway api 'mutation { deploymentRestart(id: "29e8ec39-4454-4002-b4a7-89254cc26950") }'
Then deploy the pushed lineage (origin/main bac3bd6 or later) with serviceInstanceDeployV2 once a Railway plan is selected, and verify /health and /api/ai/search/suggestions.

Effects while paused: the data API behind marketripple.in is down (frontend data pages error), scheduled ingestion/scoring does not run, SSE and quotes are down.
Measured before pausing: backend memory avg 1.85 GB (7-day max 7.06 GB), CPU avg 0.04 vCPU; Oct 1-10 egress 31.4 GB.

# TASKS.md

> Execute top-to-bottom. Check an item only after its acceptance test passes.

## 0 — Bootstrap
- [x] Scaffold `web/` Next.js and `api/` FastAPI; add strict lint/type/test commands and `.env.example`.
- [x] Add `GET /health`; run frontend + API locally.

## 1 — Pilot + sources
- [x] Acquire/build `pacoima_aoi.geojson`; programmatically prove area `<10 mi²` and add boundary test.
- [x] Create `data/sources.json`; ingest/cache pilot POIs + LA Metro + minimal ACS variables.
- [x] Produce one clipped, deterministic processed public-data fixture for Pacoima.

## 2 — FortyGuard safely
- [x] Implement typed async FortyGuard adapter, request-hash cache, resumable status polling, and fixture tests.
- [x] Implement credit ledger/governor with 500k hard reserve and `FORTYGUARD_LIVE=0` default.
- [x] With live mode explicitly enabled, measure one heatmap request's real credit delta; record it.
- [x] Cache one real Pacoima `tcm` 100m heatmap and one matching `persistence` result without breaching reserve.
- [x] Probe only the optional endpoint access actually needed; disable unsupported Premium features cleanly.

## 3 — Decision engine
- [x] Build tile feature table: heat + exposure + vulnerability + cooling opportunity; unit-test normalization/missing data.
- [x] Add versioned intervention catalog with applicability, planning cost, evidence, uncertainty, and source.
- [x] Generate >=20 evidence-backed compatible candidates from real pilot data.
- [x] Implement deterministic OR-Tools optimizer; prove cost <= budget and <=1 intervention/site for preset budgets.
- [x] Expose pilot/layers/candidates/optimize/site/methodology/data-status API routes.

## 4 — Product UI
- [x] Invoke/read **Impeccable skill**; implement the golden map information architecture it specifies.
- [x] Build map layers, ranked recommendations, budget control, KPIs, evidence drawer, methodology, and data freshness UI.
- [x] Re-run Impeccable review; fix accessibility, responsive behavior, loading/error states, and visual hierarchy.
- [x] Add grounded template explanation; optional cached LLM explanation only if it improves judging.

## 5 — Proof
- [x] Add golden Playwright E2E and assert budget changes make zero FortyGuard calls.
- [ ] Run backend unit/integration suite, frontend checks, and `scripts/validate_demo.py`.
- [ ] Deploy web + API in demo mode; run golden E2E against deployed URLs.
- [ ] Perform one final controlled live refresh only if useful and reserve remains >=500k; otherwise keep validated cache.
- [ ] Freeze demo data, verify sources/limitations/credit status, and record a 2–3 minute judge demo path.

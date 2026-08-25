# EVIDENCE

## Current verified snapshot

This section is the current judge-facing proof index. Later sections preserve the chronological
build record, so intermediate counts, model names, and unavailable capabilities there describe the
state at that task's completion and may be superseded by this snapshot or a later section.

| Requirement | Current proof |
| --- | --- |
| Official pilot boundary | `data/processed/pacoima_aoi.geojson` validates at `7.763214 mi²`, below the `10 mi²` limit. |
| Cached heat decision data | Four API layers are derived from 2,001 validated Pacoima tiles; ordinary reads make no vendor request. |
| Candidate catalog | `data/processed/pacoima_candidates.json` contains 172 unique-site candidates: 111 shade, 41 tree, and 20 cool pavement. |
| Deterministic planning | CP-SAT enforces budget and one intervention per site; four versioned scoring presets are locally re-scored. |
| Robustness semantics | The API/UI report site selection frequency across exactly four presets, never statistical confidence or probability. |
| Bounded optional evidence | Committed normalized artifacts contain 20 Street View records, 10 environmental finalists, and one satellite pavement record. Missing records remain visibly unavailable. |
| Explanation boundary | Deterministic templates are the default; optional `stealth/ox-alpha` wording is source-constrained, cached, and cannot rank or add evidence. |
| Credit boundary | The capability snapshot records `1,759,280` credits remaining and the server enforces the `500,000` reserve. Budget/scenario replanning visibly consumes `0 FortyGuard credits`. |
| UI regression | Strict TypeScript and zero-warning lint pass; 11 active component tests cover the golden workspace, keyboard tour, empty state, recovery, refresh, and zero-vendor replanning. |
| Decision log | `BUILDLOG.md` records only material runtime discoveries and architecture/product decisions; its current audit entry points readers to validated configs/artifacts rather than copying historical state forward. |
| Source registry | `data/sources.json` contains 13 unique typed sources. Heatmap, Street View, environmental, and satellite evidence now each disclose provider documentation, retrieval/data dates, retained fields, provider-terms caveat, and decision-safe limitations; all four registry tests pass. |
| Capability snapshot | The typed capability enum/manifest now records successful cached TCM, persistence, exceedance, time-of-measure, environmental, Street View, and satellite access; only Heat Intelligence remains unconfirmed. Five non-core probes reconcile exactly, credits still balance at `240,720` used plus `1,759,280` remaining, and capability tests, Ruff, and Mypy pass. |
| Scoring/config guide | `config/README.md` now defines calculation order, normalization/missing-data behavior, all component and scenario weights, candidate factor fallbacks, robustness semantics, non-scoring evidence, and each config file's authority. It explicitly separates the permitted-evidence catalog from active numeric rules. All 42 focused scoring-to-optimizer tests pass without changing hashed decision artifacts. |
| Evidence-specific scalar language | The Impeccable-reviewed tour now labels confidence as `Site-specific` instead of presenting a fixed `0.5`. Current docs describe neutral values only as evidence-dimension or candidate-specific fallbacks, and the early universal-fallback milestone is explicitly marked superseded. All 11 UI tests, strict TypeScript, and lint pass. |
| Cool-pavement availability | Support is active rather than claimed speculatively: 20 candidates each map to an exact AOI-clipped StreetsLA pavement asset with surface, positive width, and PCI category; the optimizer selects cool pavement within the supported `$5M` custom range. All 15 focused candidate/optimizer tests pass. |
| Numeric claim audit | Every displayed/API number belongs to one of the lineage classes below: vendor observation, authoritative public input, cited price/research evidence, deterministic derivation, or explicit user/config planning assumption. The 48-test traceability suite passes. |
| Heat Intelligence contract | Official FortyGuard documentation checked 2026-08-25 confirms `POST /v1/heat_intelligence` is a Premium-only asynchronous point report. The required request fields, five allowed analysis categories, status lifecycle, and temporary PDF download-link handling are recorded below; no request was made for this documentation-only task. |

Machine-readable provenance remains in `data/sources.json`, the capability snapshot in
`data/processed/fortyguard_capabilities.json`, and versioned decision assumptions in `config/`.

## Numeric claim lineage

| Numeric claim class | Authoritative lineage | Enforced proof |
| --- | --- | --- |
| Heat, persistence, exceedance, and peak time | Cached FortyGuard artifacts with analysis dates, activity/request identifiers, and SHA-256 links in `pacoima_tile_features.json` | Feature-table canonical/hash/formula tests |
| Transit activity, POIs, and ACS context | `pacoima_public_data.json`, `data/raw_manifest.json`, and dated/licensed entries in `data/sources.json` | Public/processed-data schema and join tests |
| Street, environmental, and satellite values | Exact-site normalized artifacts retaining source record hashes/IDs, image or observation dates, and endpoint limitations | Normalized evidence and decision API tests |
| Normalized component and priority scores | Raw values plus quantile metadata in the tile table; exact weights and missing rules in `config/scoring.json` and `config/scenarios.json` | Bounds, recomputation, config-hash, and four-preset tests |
| Suitability, feasibility, confidence, and impact | Exact candidate factors, suitability basis, evidence records, config hash, and formula in `pacoima_candidates.json` | Candidate factor recomputation and non-neutral-source tests |
| Planning prices and cited study ranges | `data/processed/interventions.json` source IDs, URLs, publication dates, package basis, range, and “not a quote” disclaimer | Catalog range/source-integrity tests |
| Portfolio totals and robustness | Requested budget, integer CP-SAT coefficients, selected candidate factors, and exact four-preset site counts | Determinism, budget, mutual-exclusion, and frequency tests |
| Credit counts and refresh cost | Measured usage artifacts and the balanced `fortyguard_capabilities.json` counters | Credit governor, capability, and zero-vendor replan tests |

The browser consumes only typed API responses, displays source links beside evidence, and labels
model/config outputs as modeled or planning assumptions. The 48-test numeric-lineage suite covers
feature tables, public data, price catalog, candidates, optional evidence, scenarios, optimizer,
decision API, explanations, and capability counters.

## Current Heat Intelligence API contract is verified

- Requirement: verify the current `/v1/heat_intelligence` documentation before attempting the
  optional endpoint.
- Official sources checked 2026-08-25:
  `https://docs-api.fortyguard.com/docs/heat-intelligence` and
  `https://docs-api.fortyguard.com/docs/limitations`.
- Access: `POST https://api.fortyguard.com/v1/heat_intelligence` is documented as API Premium only;
  a credit balance alone does not prove access.
- Required request fields: `latitude`, `longitude`, `temperature` in °C, `date` in `YYYY-MM-DD`,
  and an `analysis` array containing a subset of `geographic`, `environmental`, `urban`, `events`,
  and `anthropogenic`.
- Date/location constraints: the date must be from 2019-01-01 through 12 hours beyond the current
  time, should match the source heatmap observation, and the current release is US-only.
- Result lifecycle: submission returns an `activity_id`; bounded polling uses
  `GET /v1/status/{activity_id}` until terminal `Completed` or `Failed`. A completed response returns
  `data.result.download_link`, a temporary signed PDF link that must be downloaded immediately and
  never logged or shared.
- Product boundary: any report may support a top recommendation only. It must not rank candidates,
  alter optimizer inputs, or become a demo dependency.
- Credit/probe proof: this verification made **zero FortyGuard requests**. The committed counters
  therefore remain **240,720 used / 1,759,280 remaining**, above the **500,000** reserve.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_capabilities.py` validates that the
  report remains disabled and unconfirmed until a successful governed request is cached.

## Pacoima AOI is below the FortyGuard limit

- Requirement: committed Pacoima AOI is valid WGS84 GeoJSON and smaller than 10 mi².
- Artifact: `data/processed/pacoima_aoi.geojson`.
- Source: City of Los Angeles, `Neighborhood Councils (Certified)`, feature `PACOIMA NC`
  (`OBJECTID=64`, `NC_ID=7`), retrieved 2026-08-20.
- Method: Shapely geometry validation followed by area calculation in UTM zone 11N
  (`EPSG:32611`).
- Result: **7.763214 mi²**, below the 10 mi² hard limit and 9.5 mi² preferred ceiling.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_boundary.py` → `3 passed`.
- Artifact SHA-256: `D166687F16077F8FA896B8B65BAD28F985A7243361B97F3DA8F4F6C59135D2E1`.

## Public exposure and vulnerability sources are integrated

- Requirement: integrate at least two public exposure/vulnerability sources into a committed,
  demo-ready Pacoima artifact.
- Artifact: `data/processed/pacoima_public_data.json`.
- Sources: current LA Metro GTFS, LA Metro April 2024 patronage, 2024 ACS 5-year estimates and
  TIGER tract geometry, LAUSD school sites, Los Angeles City parks, and LAPL branches. Retrieval
  URLs, dates, fields, licenses, and limitations are recorded in `data/sources.json`; raw hashes
  and counts are recorded in `data/raw_manifest.json`.
- Result: 43 POIs (30 schools, 11 parks, 2 libraries), 8 current Metro bus routes, 111 transit
  stops with published patronage, and 32 ACS tracts intersecting and clipped to the official
  Pacoima AOI. ACS numerator fields retain their explicit population/household denominators.
- Determinism proof: `.venv\Scripts\python.exe -m scripts.build_public_fixture --check` rebuilt
  the fixture from cache and matched it byte-for-byte.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_processed_data.py` → `2 passed`.
- Artifact SHA-256: `705BC38A92026E7AA5009D1111570E256A2FF7211C59DB4BBD809AF13279DB42`.

## One real FortyGuard heatmap cost is measured

- Requirement: with live mode explicitly enabled, submit one minimal heatmap request, measure its
  real before/after credit delta, and preserve the 500,000-credit hard reserve.
- Artifact: `data/processed/fortyguard_credit_measurements.json`; the server-side raw response,
  request journal, activity link, and ledger remain cached under ignored `data/raw/fortyguard/`.
- Request: Pacoima official 7.763214 mi² AOI, `tcm`, 100 m, one hour beginning
  2024-07-15 at 14:00; canonical request hash
  `b10fe0b3fd039fa01ccce197f0aaa8167c3c51f6dfce1b0678a363a39fa8fdd7`.
- Result: activity `fd894ae2-8891-4739-8e4e-d5ca7bc9b889` completed with 2,001 validated
  GeoJSON tiles. Current-cycle usage changed from **0** to **4,220**, an observed cost of
  **4,220 credits**. **1,995,780 credits remained**, above the 500,000 reserve.
- Idempotency proof: after strict validation exposed a runtime-only GeoJSON `id` field, the
  command resumed the same cached activity ID; it did not submit another heatmap request.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_fortyguard.py
  api/tests/test_credits.py api/tests/test_live_measurement.py` → `11 passed`.
- Artifact SHA-256: `9E3B331310A7CE2F4563225B37F9C8EFDD8C0D311D534437CBDADCB7AF7CB17F`.

## Real Pacoima TCM and persistence layers are cached

- Requirement: cache at least one real successful FortyGuard TCM dataset and one matching
  persistence dataset at 100 m without breaching the credit reserve.
- Artifact: `data/processed/pacoima_fortyguard_heatmaps.json`, a deterministic 4,401,985-byte
  offline artifact validated by `PacoimaHeatmapArtifact`. Raw responses and activity metadata are
  retained under ignored `data/raw/fortyguard/` on D:.
- Match proof: both completed layers contain **2,001 tiles** with identical ordered GeoJSON feature
  IDs and polygon geometries, use the official Pacoima AOI, use 100 m granularity, and share the
  2024-07-15 date context. The TCM layer represents 14:00; daily persistence counts values above
  the versioned 30 °C planning threshold in `config/fortyguard_heatmaps.json`.
- Live proof: TCM activity `fd894ae2-8891-4739-8e4e-d5ca7bc9b889` and persistence activity
  `840ec657-3a84-4c7e-9a55-1991333d8e83` both completed. Each observed delta was **4,220 credits**;
  cumulative cycle usage was **8,440**, leaving **1,991,560 credits**, above the 500,000 reserve.
- Request hashes: TCM `b10fe0b3fd039fa01ccce197f0aaa8167c3c51f6dfce1b0678a363a39fa8fdd7`;
  persistence `31f95902a1ee11fd073b3be2f2afdb4b083cb3a3c9ff50182efbab013a4dcd81`.
- Test proof: focused adapter, governor, live-measurement, and real-data suite → `13 passed`; it
  validates request/config agreement, tile alignment, credit deltas, deterministic serialization,
  numeric layer values, and absence of credential/account fields.
- Artifact SHA-256: `A76E1E9C0310B4725D8AB0A37C12C3A5FD3F2E70FAF8B28A7EFB98A020BEF27A`.

## Unneeded optional FortyGuard capabilities are explicitly disabled

- Requirement: probe only optional endpoint access needed by the core MVP and disable unconfirmed
  Premium features cleanly without inferring access from the credit balance.
- Artifact: `data/processed/fortyguard_capabilities.json`, validated by
  `CapabilityManifest`/`CapabilityRecord` and loaded through a fail-visible feature guard.
- Result: required cached TCM and persistence capabilities are enabled with confirmed runtime
  access. Exceedance, environmental parameters, satellite segmentation, street-view segmentation,
  and Heat Intelligence are disabled with explicit reasons/dependencies and `access=unconfirmed`.
  Calling `require_enabled` for any disabled feature raises a useful `FeatureDisabledError`.
- Credit proof: **zero optional live probes** were made because none is required for the core
  feature table or acceptance path. Usage therefore remained **8,440** with **1,991,560 credits**
  remaining, preserving the 500,000 reserve.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_capabilities.py` → `2 passed`;
  the tests cover the complete capability set, enabled cached layers, disabled/unconfirmed states,
  fail-visible guards, zero optional probes, and balanced credit counters.
- Artifact SHA-256: `118CF5E0E00F2CD8C17BC7A3C835C3E81CB2E73386817068F37A8009A024C269`.

## Deterministic tile feature table integrates the four decision dimensions

- Requirement: build the base tile feature table with heat, exposure, vulnerability, and cooling
  opportunity; unit-test normalization and missing-data behavior.
- Artifact: `data/processed/pacoima_tile_features.json`, generated by
  `scripts/build_feature_table.py` from the frozen real heatmaps, processed public data, and
  versioned `config/scoring.json`.
- Result: **2,001 unique, ordered heat tiles** retain raw TCM temperature and persistence hours,
  published Metro patronage evidence, POI/site references, area-weighted ACS tract-context rates,
  normalized component scores, the modeled priority score, source hashes, and limitations.
- Join proof: all **111 transit stops** and **43 POIs** are represented; no records are unmatched.
  Two AOI-edge stops outside the returned heat coverage by 3.2 m and 14.6 m are assigned to the
  nearest tile under the configured 25 m tolerance and explicitly flagged as proximity joins.
- Truth/uncertainty proof: ACS population is labeled tract context and never claimed as tile
  population. Patronage uses the maximum published ons+offs across retained DX/SA/SU categories
  without inventing category meanings. Cooling opportunity means actionable public/transit siting
  evidence, not inferred canopy or surface conditions.
- Missing-data proof: tract `06037980021` reports a 0/0 vehicle-household denominator, so
  `no_vehicle_rate` remains missing on 433 intersecting tiles. The raw and normalized fields stay
  `null`, `missing_fields` identifies them, and vulnerability composites reweight only their other
  available inputs.
- Normalization proof: deterministic 2nd/98th-percentile winsorized min-max bounds and all scoring
  weights live in `config/scoring.json`. Unit tests cover ordinary, outlier, constant, and missing
  inputs plus available-weight renormalization.
- Test proof: focused feature/heat/public-data suite → `7 passed`; strict Mypy and Ruff pass;
  `.venv\Scripts\python.exe -m scripts.build_feature_table --check` matches byte-for-byte.
- Artifact SHA-256: `5DC46CE16B5FBD4D7A939EE4A3BD26A5FD2B333C2E2E96AD30048C168415F4A9`.
- Scoring-config SHA-256: `9AB6234C4222A680AD011687BCE3F39C3AA9E107709DA9AA26F07B3C2AAC20CD`.

## Versioned intervention catalog is complete and traceable

- Requirement: define the three MVP intervention families with executable applicability rules,
  disclosed planning costs, evidence, uncertainty, sources, and maintenance/lifespan notes.
- Artifact: `data/processed/interventions.json`, validated by the strict
  `InterventionCatalog`/`InterventionDefinition` boundary models in
  `api/app/services/interventions.py`.
- Result: the version 1.0 catalog defines shade structures, tree canopy, and cool pavement with
  positive USD planning estimates inside explicit low/high ranges. The shared disclaimer and each
  cost basis state that values are rounded screening allowances, not contractor quotes, bids, or
  construction estimates.
- Applicability proof: shade structures screen only published transit stops; tree packages screen
  only mapped schools and parks; cool pavement requires a verified public corridor or paved
  surface. Every family lists preconstruction checks and exclusion rules, so the catalog does not
  infer existing shade, canopy gaps, planting feasibility, or pavement from a hot tile or POI.
- Evidence proof: six cataloged sources resolve all cost-scope, qualitative-benefit, and lifecycle
  references. They include LADOT and LA Metro shade guidance, EPA and StreetsLA tree guidance, the
  2024 Pacoima observational cool-pavement study, and StreetsLA's lifecycle caution. Unknown source
  publication dates remain `null` rather than being inferred.
- Claim proof: benefits are qualitative and transfer limits prohibit applying cited observations
  as site forecasts. Uncertainty is explicit, no candidate-level cooling outcome is promised, and
  tests reject unknown source IDs and planning estimates outside their ranges.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_interventions.py` → `3 passed`;
  focused Ruff and strict Mypy checks pass.
- Artifact SHA-256: `4969DDD8498C471855FAE0BDC335FF85804979E6E93CE74E753B8E882661A932`.

## Real Pacoima data produces at least 20 compatible candidates

- Requirement: deterministically generate at least 20 evidence-backed intervention/site candidates
  from the frozen real pilot inputs.
- Artifact: `data/processed/pacoima_candidates.json`, generated by
  `scripts/build_candidates.py` from the tile feature table, processed public data, intervention
  catalog, and versioned `config/candidates.json`.
- Result: **152 candidates at 152 unique authoritative sites**: 111 shade-structure screenings at
  LA Metro stops and 41 tree-canopy screenings at 30 LAUSD schools plus 11 City park records. Each
  has a real site geometry, representative real FortyGuard tile, catalog planning cost, modeled
  benefit/equity scores, five structured evidence records, and traceable input-artifact hashes.
- Compatibility proof: candidate site types are checked against the catalog at build time and in
  tests. No cool-pavement candidate is generated because the cached pilot inputs contain no direct
  public paved-surface/corridor geometry; heat or proximity to a POI is not substituted as surface
  evidence.
- Spatial proof: point sites use their containing tile. Eleven polygon sites intersect multiple
  tiles and use the versioned rule: highest modeled priority, then heat, then lowest numeric tile
  ID. This represents the hottest priority portion of the real site without duplicating it.
- Historical scoring proof: at this milestone, before exact-site enrichment, feasibility and
  confidence both used the disclosed neutral fallback. The later evidence-specific section below
  supersedes that state; the fallback was never a probability or measured effect.
- Determinism proof: `.venv\Scripts\python.exe -m scripts.build_candidates --check` rebuilds the
  398,557-byte artifact and matches it byte-for-byte.
- Test proof: candidate, feature-table, and intervention-catalog suite → `9 passed`; focused Ruff
  and strict Mypy checks pass.
- Artifact SHA-256: `E1C7B55AB1EB466FD2D79D3DEA77068811B12215FD2D7939B5775D60DA12A5D4`.
- Candidate-config SHA-256: `1D1F4027DB5F5B84744AEEE435FF170AD20E2038683FC4B6B08877CC9E84FBCA`.

## OR-Tools optimizer is deterministic and budget/site feasible

- Requirement: implement a deterministic OR-Tools CP-SAT portfolio optimizer and prove
  `total_cost <= budget` plus at most one intervention per site for every preset budget.
- Implementation: `api/app/services/optimizer.py` uses locked OR-Tools 9.15.6755, integer USD
  costs, Boolean candidate variables, a hard budget constraint, and one `sum(x) <= 1` constraint
  per site. `config/optimizer.json` versions budget bounds, presets, the `1,000,000` objective
  scale, solve limit, and claim-safe score definitions.
- Objective proof: each primary integer coefficient is the candidate's frozen tile priority score
  multiplied by its disclosed feasibility and confidence screening scalars, then integer-scaled.
  A bounded candidate-ID secondary term resolves exact ties without overriding one unit of the
  primary objective.
- Determinism proof: the solver uses one worker, fixed seed, fixed search, sorted candidate IDs,
  and requires `OPTIMAL` status. Tests reverse the complete candidate input order and obtain the
  identical typed result.
- Preset results: `$250,000` selects 5 sites costing `$250,000`; `$500,000` selects 10 sites
  costing `$500,000`; `$1,000,000` selects 20 sites costing `$1,000,000`. All have zero budget
  overrun and unique selected site IDs. Outputs include unused budget, category counts, modeled
  impact, and mean selected vulnerability-score context.
- Site-exclusion proof: a synthetic input with two intervention options at the same site and one
  unrelated option has budget for all costs but selects exactly one same-site option, proving the
  constraint independently of the current one-candidate-per-site artifact.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_optimizer.py` → `3 passed`;
  focused Ruff and strict Mypy checks pass.
- Optimizer-config SHA-256: `85388C02C2A2DF7C4D2F32EE42D948DD2878ED29A9D3066A151D09768EE844AF`.

## Complete decision API is typed and offline-capable

- Requirement: expose pilot, layer, candidate, optimization, site, methodology, and data-status
  routes using committed demo data.
- OpenAPI proof: the application publishes `GET /v1/pilot`, `GET /v1/layers/{layer}`,
  `GET /v1/candidates`, `POST /v1/optimize`, `GET /v1/sites/{site_id}`,
  `GET /v1/methodology`, and `GET /v1/data-status`.
- Layer proof: heat, persistence, exposure, and vulnerability each return a schema-validated
  GeoJSON FeatureCollection with **2,001** real tile geometries and layer-specific typed
  properties. Raw temperature/persistence and exposure/ACS context remain distinguishable from
  normalized modeled scores and missing values.
- Decision proof: `/v1/candidates` returns all 152 traceable candidates; `/v1/sites/{site_id}`
  joins a site's candidate to its selected real tile and full intervention evidence/cost/source
  definition; `/v1/methodology` exposes the versioned scoring, candidate, optimizer, and
  intervention configurations.
- Offline/no-credit proof: `/v1/optimize` loads only the committed candidate artifact and returns
  the deterministic CP-SAT result. The integration test mocks both FortyGuard submission and
  credit-usage methods and proves neither is called during a `$500,000` optimization.
- Freshness proof: `/v1/data-status` explicitly reports `mode=cached_demo`,
  `external_calls_on_read=false`, analysis/public-data dates, capability states, **8,440 credits
  used**, **1,991,560 remaining**, and the 500,000 hard reserve.
- Boundary/error proof: the API rejects out-of-range budgets with HTTP 422 and unknown sites with
  HTTP 404 rather than substituting data.
- Test proof: `.venv\Scripts\python.exe -m pytest api/tests/test_decision_api.py
  api/tests/test_app.py` → `4 passed`; focused Ruff and strict Mypy checks pass.

## Impeccable golden-map information architecture is implemented

- Requirement: invoke/read the mandatory Impeccable skill before UI work and implement its
  golden-map hierarchy using the repository's product/design context.
- Preflight proof: the installed Impeccable `SKILL.md` was read in full; its context loader returned
  non-placeholder `PRODUCT.md` and `DESIGN.md`; the product-register reference was loaded; and the
  required preflight was declared with context/product/command gates passing, shape not required,
  and bitmap imagery skipped because the real geospatial data is the product visual.
- Implementation: `web/components/planning-shell.tsx` and its scoped CSS replace the generated
  Next.js page with a persistent civic/data header, ranked portfolio rail, dominant Pacoima map
  rendering surface, budget command bar, layer dock, KPI summary, and evidence inspector. The
  hierarchy follows the desktop fixed-fluid map model and collapses structurally for tablet/mobile.
- Design-system proof: colors use restrained OKLCH heat/cooling semantics; Public Sans, Inter, and
  JetBrains Mono are self-hosted by Next; tonal layers and 1px outlines replace decorative cards or
  shadows; visible copy avoids unsupported outcome claims and distinguishes cached, observed, and
  modeled values.
- Data-truth proof: visible planning figures come from the frozen real artifacts and `$500k`
  optimizer result. The placeholder rendering surface does not draw invented geography or place a
  marker at an invented coordinate; the next task will connect it to the real typed map layers.
- Accessibility proof: semantic header/main/asides/sections, labeled navigation/status/legend,
  visible focus treatment, a keyboard skip link, high-contrast states, and reduced-motion handling
  are present. Breakpoints at 78rem, 52rem, and 34rem prevent desktop panels from breaking the
  mobile flow.
- Test proof: `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build` all pass; Next.js
  successfully prerenders `/` as static content.
- Visual-QA limitation: the in-app browser control surface was unavailable in this session, so no
  screenshot review is claimed. The later mandatory Impeccable review task remains the explicit
  visual/accessibility correction pass.

## Golden planning UI is functional against the cached decision API

- Requirement: build map layers, ranked recommendations, budget control, KPIs, site evidence,
  methodology, and data-freshness UI for the Pacoima golden path.
- Map proof: `web/components/map-view.tsx` uses MapLibre GL with the real Pacoima boundary and the
  API's 2,001 GeoJSON tiles. Heat, persistence, exposure, and vulnerability load on demand and are
  runtime-validated before rendering. Selected portfolio sites use their committed coordinates;
  the map has an offline base surface and does not invent streets or geographic detail.
- Decision proof: the `$250k`, `$500k`, and `$1M` controls POST only the budget to the deterministic
  `/v1/optimize` route. The real proxy smoke returned the `$1M` optimal portfolio with 20 selected
  sites, `$1,000,000` total cost, and modeled impact `3.85278254`; the UI reports zero vendor calls.
- Evidence proof: recommendations are ordered by the candidate's disclosed modeled-impact formula;
  selecting one loads its typed site/tile/intervention record. The drawer exposes observed heat,
  persistence, published patronage when present, modeled vulnerability, cost/range, confidence,
  candidate evidence statements, source links, and the full pilot limitations without unsupported
  temperature or population claims.
- Freshness/API-boundary proof: the header reads cached/live mode, heat date, and credits from
  `/v1/data-status`. Zod schemas validate every response consumed by the browser. A same-origin,
  allow-listed Next route forwards only the seven decision API shapes and returns a visible 502
  when FastAPI is unavailable; server configuration remains outside client code.
- Real-contract proof: with the local FastAPI fixture server, `COOLSPOT_API_TEST_URL=http://127.0.0.1:8000
  npm test` validated pilot, candidates, status, methodology, all four complete layer responses,
  optimization, and selected-site detail → `3 passed` across two test files.
- Interaction proof: frontend tests toggle persistence, change the budget to `$1M`, assert the
  20-site result, and assert no request URL contains `FortyGuard`. `npm run check` passes lint,
  Next route type generation, strict TypeScript, and `2 passed` UI tests (`1` gated real-contract
  test skipped without its explicit local-API environment variable).
- Build/smoke proof: `npm run build` passes with Next.js 16.3.1, statically prerenders `/`, and emits
  the dynamic allow-listed proxy route. Local HTTP checks returned 200 for `/`, the proxied pilot,
  the 851,002-byte real heat layer, and the proxied `$1M` optimization.
- Visual-QA limitation: the Browser plugin's required control tool was not exposed in this session,
  so no screenshot or physical-device claim is made for this implementation proof.

## Impeccable technical review findings are resolved

- Requirement: re-run the mandatory Impeccable review and fix accessibility, responsive behavior,
  loading/error states, and visual hierarchy before continuing.
- Review proof: the Impeccable `audit` rubric was applied across accessibility, performance,
  theming, responsiveness, and anti-patterns, followed by its `harden`, `adapt`, and `polish`
  guidance. The initial code audit scored **15/20 (Good)** with no P0 blockers; the corrected code
  audit scores **18/20 (Excellent)**. The remaining two points reflect the intentionally single
  dark theme and unavailable live-browser/device inspection, not a known acceptance failure.
- Accessibility proof: the interactive MapLibre surface is a named region rather than an image
  role containing hidden interactive descendants. Layer/budget controls expose pressed, disabled,
  busy, and live states; keyboard focus remains visible; forced-colors selections have non-color
  outlines; skip navigation and semantic landmarks remain intact.
- Responsive proof: all compact layer, preset, slider, error, and map controls meet the 44px target
  floor. The mobile breakpoint raises previously tiny operational labels to 14px, preserves every
  core feature in a single-column flow, and long site/methodology/source text wraps without causing
  horizontal overflow.
- Loading/error proof: the initial page uses a stable three-column loading shell instead of a
  layout-shifting blank state. A failed layer request retains the prior layer; a failed site request
  cannot pair new candidate copy with stale site evidence; a failed budget update restores the
  prior portfolio budget. Each operation announces a specific, dismissible recovery message while
  the rest of the valid workspace remains usable. Map/WebGL import failure has an explicit fallback.
- Automated proof: the new failure-path test forces a persistence HTTP 503 and verifies the full
  recommendation workspace remains present, Heat remains selected, and the useful upstream message
  is announced. `npm run check` passes ESLint, Next route type generation, strict TypeScript, and
  `3 passed` UI tests (`1` gated real-API contract test skipped by default). `npm run build` passes
  and prerenders `/` on Next.js 16.3.1.
- Visual-review limitation: the Browser skill was read and its required control tool was searched
  for, but it was not exposed. No screenshot, exact rendered contrast, or physical-device claim is
  made; code-level review and automated behavior are the available proof in this environment.

## Selected-site explanations are deterministic and grounded

- Requirement: answer “Why this site?” from structured evidence, with an optional cached LLM path
  only when it materially improves judging.
- Grounding proof: `api/app/services/explanations.py` accepts only a validated candidate, its joined
  tile/intervention, and a deterministic portfolio. It verifies the candidate is selected at the
  submitted budget, then copies the candidate's five evidence statements and constructs a typed
  summary from exact site, budget, selected-count, priority, feasibility, confidence, and modeled
  impact fields. The response always labels `mode=template`.
- Claim-safety proof: every response includes three explicit limitations: no predicted temperature
  reduction, people protected, or guaranteed outcome; site-specific intervention uncertainty; and
  planning costs/ranges as assumptions rather than contractor quotes. A candidate outside the
  portfolio is rejected with HTTP 409 instead of receiving a plausible-sounding explanation.
- No-credit proof: the API explanation test mocks FortyGuard submission and usage methods and proves
  both call counts remain zero. The explanation path recomputes only the local CP-SAT portfolio and
  reads committed evidence.
- UI proof: the evidence panel exposes an inline, keyboard-accessible “Why this site?” action with
  loading, refresh, error, evidence-used, and limitations states. Responses are retained by
  candidate-plus-budget key, so an explanation cannot be reused for a different scenario. The
  interaction stays in the evidence flow rather than adding a modal or decorative page.
- Backend test proof: `.venv\Scripts\python.exe -m pytest api\tests\test_decision_api.py` →
  `4 passed`; focused Ruff and strict Mypy checks pass.
- Frontend test proof: `npm run check` passes lint, strict types, and `4 passed` UI tests. With the
  real local API enabled, the complete frontend contract suite including explanation → `5 passed`.
  `npm run build` passes and prerenders `/`.
- Runtime proxy proof: the built Next app POSTed through the allow-listed same-origin route for
  `shade_structure:metro-stop:10787` at `$500,000` and returned HTTP 200, `mode=template`, five
  evidence reasons, and three limitations.
- LLM decision: no LLM mode was added. The deterministic response already covers the judging need;
  adding a provider would introduce latency, configuration, cache, and hallucination risk without
  new evidence or decision capability.

## Golden Playwright path makes zero FortyGuard calls

- Requirement: exercise the judge's real browser path and prove budget changes use only committed
  data rather than spending FortyGuard credits.
- Browser proof: `web/e2e/golden-path.spec.ts` starts the fixture-backed FastAPI service with
  `FORTYGUARD_LIVE=0` and the real Next app, then loads Pacoima, verifies the cached-analysis state
  and `$500,000`/10-site portfolio, switches to the 2,001-tile persistence layer, re-optimizes to
  `$1,000,000`/20 sites, selects another recommendation, opens source methodology, and generates
  its deterministic evidence-and-limitations explanation.
- Zero-call proof: the test records every browser request and asserts none contains `FortyGuard`.
  It also proves both optimize POST bodies (`500000` and `1000000`) traversed the local proxy and
  compares `/data-status` before and after: `external_calls_on_read=false`, credits used remain
  `8,440`, and credits remaining remain `1,991,560`.
- Automated proof: with browser binaries stored under the D: workspace,
  `PLAYWRIGHT_BROWSERS_PATH=D:\COOLSPOT AI\.playwright-browsers npm run test:e2e` → `1 passed`
  in Chromium. `npm run check` passes ESLint, Next route generation, strict TypeScript, and `4`
  unit tests (`1` opt-in real-contract test skipped); `npm run build` passes and prerenders `/`.

## Full local verification and demo API validation pass

- Requirement: run the complete backend unit/integration suite, frontend checks, and the external
  demo validator before deployment work.
- Backend proof: `.venv\Scripts\python.exe -m pytest` collected the configured API suite and
  returned `41 passed` across boundary, public-data processing, heat fixtures, candidates, scoring,
  capabilities, credit governance, FortyGuard fixture integration, optimizer, decision API, and
  explanation behavior. `.venv\Scripts\python.exe -m ruff check .` and strict configured Mypy both
  pass.
- Frontend proof: `npm run check` passes ESLint with zero warnings, Next route generation, strict
  TypeScript, and `4 passed` Vitest checks (`1` explicitly gated real-API contract test skipped).
- Validator proof: the previously specified but missing `scripts/validate_demo.py` now validates
  deployed HTTP responses with the same Pydantic boundary models as the API. Against a real local
  Uvicorn process it returned: `PASS: Pacoima, Los Angeles; 4 layers; 152 candidates; budgets
  $500,000/$1,000,000; credits unchanged at 1,991,560 remaining`.
- Acceptance coverage: the validator checks health, AOI/pilot contract, all non-empty layer
  contracts, candidate counts, methodology, deterministic repeated optimization, cost at or under
  budget, at most one intervention per site, selected-site lookup, grounded explanation identity,
  hard credit reserve, cached read mode, and identical before/after credit counters.
- Validator quality proof: focused Ruff and `mypy --strict scripts\validate_demo.py` both pass. The
  script accepts `--base-url`/`COOLSPOT_API_BASE_URL` and can be invoked directly by file path from
  the repository, including on the current Windows workspace.

## Production map rendering is verified

- Pre-deployment visual review exposed a blank map even though MapLibre controls had mounted. The
  camera was correctly fitted, but runtime inspection showed `styleLoaded=false`, zero source
  features, and zero rendered features after 15 seconds.
- The failure matched MapLibre's documented Next.js GeoJSON worker regression. Pinning
  `maplibre-gl` to the last known-good `5.16.0` release restores the committed Pacoima boundary,
  heat tiles, and selected-site markers without adding a basemap or network dependency.
- Readiness is now tied to MapLibre's `idle` event after source processing, and the golden E2E
  asserts `data-map-state=ready`. It can no longer pass merely because zoom controls appeared over
  a blank canvas.
- Production runtime proof: the standalone build reported `loaded=true`, `styleLoaded=true`,
  `4,690` queryable source feature instances, and `2,109` rendered analysis feature instances in
  the current viewport. A captured local production screenshot visibly shows the Pacoima boundary,
  colored heat grid, and teal portfolio markers.
- Final proof against the same production origin: `scripts/validate_demo.py` passes all four layers,
  152 candidates, both golden budgets, and unchanged `1,991,560` remaining credits; Playwright's
  strengthened golden path returns `1 passed`. Frontend check and standalone build also pass.

## Geographic context, governed refresh, and optional AI explanations are verified

- Map proof: the production MapLibre view now draws the validated FortyGuard tile grid and selected
  recommendations over a recognizable OpenStreetMap street basemap. The same-origin tile route
  validates z/x/y, identifies COOLSPOT to the provider, caches successful PNG responses, retains
  visible OpenStreetMap attribution, and fails without removing the committed analytical layers.
- Render proof: map readiness requires the `analysis-layer` GeoJSON source to be loaded with at
  least one queryable feature, independent of basemap availability. A 1920x1080 production capture
  visibly shows Pacoima streets/freeways/place labels, the AOI, heat cells, portfolio markers, the
  active-site ring, the exact-value hover instruction, and attribution. The proxied tile smoke test
  returned HTTP `200`, `image/png`, and 7,173 bytes.
- Refresh proof: `POST /v1/refresh` requires a constant-time checked administrator token, exact
  `FORTYGUARD_LIVE=1`, a server-side API key, a non-future date within 365 days, and a conservative
  two-request credit authorization before submission. One coordinator prevents concurrent jobs;
  canonical request hashes prevent duplicate submissions; current usage is checked around each
  job; the 500,000 reserve remains mandatory; staged artifacts preserve the last validated cache
  if rebuilding fails. The UI collects the token without storing it and polls explicit
  idle/running/completed/failed/unavailable states.
- Refresh test proof: an invalid admin token returns HTTP 401 before `fetch_credit_usage` is called.
  The coordinator preflight test authorizes exactly two known-cost heatmap shapes at an estimated
  8,440 credits while reporting 1,991,560 remaining and a 500,000 reserve. No live FortyGuard call
  was made during development verification.
- AI proof: when `EXPLANATION_MODE=openrouter` and `OPENROUTER_API_KEY` are configured, only the
  deterministic summary/evidence/limitations payload is sent to
  `google/gemma-4-26b-a4b-it:free`. Temperature-reduction, guaranteed-outcome, people-protected,
  lives-saved, or novel-number output is rejected. Only the narrative summary can change; evidence,
  limitations, ranking, and optimization remain deterministic. Valid output is cached by model and
  evidence hash; unavailable, malformed, unsafe, or unconfigured output falls back visibly to the
  template.
- Final automated proof: `.venv\Scripts\python.exe -m pytest` returns `45 passed`; Ruff and strict
  Mypy pass; `npm run check` passes lint, strict types, and `4 passed` UI tests (`1` opt-in contract
  test skipped); `npm run build` passes with the basemap and COOLSPOT API routes; the production
  `scripts/validate_demo.py` result passes four layers, 152 candidates, both budgets, and unchanged
  credits; hosted-origin Playwright returns `1 passed`.

## Live-refresh connectivity failures are safe and actionable

- A real user refresh attempt failed during the read-only credit-usage preflight because the local
  API process could not reach FortyGuard. Logs prove the exception occurred before either paid TCM
  or persistence submission; current usage remained `8,440` and remaining credits `1,991,560`.
- Network transport failures are now converted to a stable vendor-boundary error. The refresh API
  returns HTTP `503` with an explicit statement that no paid jobs were submitted and that cached
  evidence remains active, instead of leaking an internal HTTP 500.
- The API was restarted with vendor network access. An authenticated read-only usage check then
  returned `8,440` used and `1,991,560` remaining; it did not submit a heatmap activity.
- Automated proof: `.venv\Scripts\python.exe -m pytest` returns `48 passed`; the failure-path tests
  prove zero `submit_heatmap` calls, failed status retention, safe transport messaging, and the HTTP
  `503` response contract. Ruff and strict Mypy pass.

## A completed refresh updates the full decision workspace

- Real refresh proof: the authorized 20 August 2026 refresh completed both TCM and persistence
  activities. Usage moved from `8,440` to `16,880` credits, exactly the conservative two-job
  estimate, leaving `1,983,120`, well above the `500,000` hard reserve.
- Artifact proof: the active heatmap, tile-feature, and candidate artifacts now carry the refreshed
  date and changed observed heat, persistence, normalized scores, candidate benefits, and ranking
  inputs. All three are deterministically serialized and their SHA-256 provenance chain validates.
- Application proof: after the coordinator reports completion, the client refetches pilot metadata,
  data status, methodology, candidates, the heat layer, the selected site, and reruns CP-SAT at the
  user's current budget. Old layer and explanation caches are cleared. The UI confirms that the map,
  scores, recommendations, and portfolio were recalculated.
- AI proof: `EXPLANATION_MODE=openrouter` is active and “Run AI again” bypasses the file cache while
  asking Gemma for alternative wording. A real provider probe returned HTTP `429` from the free
  model; the UI now identifies that temporary rate limit and shows the deterministic grounded
  fallback instead of implying that the button did nothing.
- Reliability proof: analytical GeoJSON readiness no longer depends on the optional street basemap
  succeeding. The isolated browser test passed while basemap requests returned visible HTTP `502`
  errors, proving the core map and golden path remain operational without tile-provider access.
- Final automated proof: backend Pytest returns `49 passed`; Ruff and strict Mypy pass; frontend
  lint, strict TypeScript, and `6` Vitest tests pass (`1` opt-in contract test skipped); the production
  Next build passes; `scripts/validate_demo.py` passes 4 layers, 152 candidates, both golden budgets,
  and unchanged `1,983,120` credits; production-origin Playwright returns `1 passed`.

## Ox Alpha is the active grounded explanation model

- OpenRouter's live public model catalog returned the exact ID `stealth/ox-alpha`, display name
  `Ox Alpha`, and zero prompt/completion pricing on 22 August 2026. Its metadata reports mandatory
  reasoning with `low` support, so COOLSPOT requests low reasoning and reserves enough completion
  tokens for the user-facing paragraph.
- Configuration proof: the server default, local runtime environment, committed environment
  example, tests, and UI all use `stealth/ox-alpha`. The UI renders the model ID returned by the
  explanation API rather than a hardcoded provider/model label. Changing the model also changes the
  existing model-aware cache key, so prior Gemma wording cannot be served as Ox Alpha output.
- Real provider proof: `POST /v1/sites/metro-stop%3A10794/explanation` returned HTTP `200`, mode
  `openrouter`, model `stealth/ox-alpha`, no fallback reason, five unchanged evidence records, and
  three unchanged limitations. The model did not participate in ranking or optimization.
- Grounding proof: numeric validation now admits numbers from every structured field actually sent
  to the model (summary, evidence, and limitations), rejects any number absent from those fields,
  and distinguishes prohibited positive impact claims from explicit negative limitations such as
  “does not predict people protected.”
- Automated proof: backend Pytest returns `50 passed`; Ruff passes; strict Mypy passes across `40`
  source files; frontend lint, strict TypeScript, and `6` Vitest tests pass (`1` opt-in contract test
  skipped); the production Next build compiles successfully.

## Trust, onboarding, local price context, and site imagery

- A four-step first-run story now explains the public outcome, evidence chain, budget decision, and
  site audit for residents, investors, and government users. It is skippable, stored locally after
  dismissal, and replayable from “How it works.”
- Local price proof is explicit rather than overstated. Shade uses LADOT's approximately `$50,000`
  traditional-shelter installation reference. Tree packages disclose the City's published 2016
  `$425` planting plus `$650/tree/year` establishment-watering baseline (`$2,375` over three years)
  and explain why COOLSPOT's broader allowance is higher. Cool pavement discloses Los Angeles's
  `$191,000` FY 2016-17 appropriation for fifteen one-block installations and that Pacoima's later
  site-level prices were not published. Every displayed amount remains a planning allowance, not an
  exact selected-site bid.
- FortyGuard street-view activity `eb918f6d-b360-4fa1-aa34-55e960dedf5f` completed for exact site
  `metro-stop:10794`. The cached real frame is dated `2024-10-01` and includes original imagery, a
  segmented image, and eight coverage classes. Usage moved from `16,880` to `25,480`, an observed
  `8,600`-credit delta, leaving `1,974,520`, safely above the `500,000` reserve.
- Selecting any recommendation now opens a floating street-context surface. All 20 sites in the
  deterministic `$1M` portfolio have exact-coordinate cached imagery: the original result was
  reused and 19 new jobs completed at the observed `8,600` credits each. Usage moved from `25,480`
  to `188,880`, leaving `1,811,120`, safely above the `500,000` reserve. Sites outside that portfolio
  show a verified-unavailable state and make no paid call. The request lifecycle is recorded in the
  credit ledger and the UI retains each frame date, vendor source, and field-verification limitation.
- AI output is constrained to a short, three-sentence target. Core links for FortyGuard heatmaps, LA
  Metro patronage, Census ACS, and intervention-specific price/benefit evidence appear directly with
  the explanation; detailed evidence records and limitations remain expandable. The interface does
  not claim 100% certainty and clearly separates observed, modeled, and unverified inputs.
- Automated proof: backend Pytest returns `51 passed`; Ruff passes; strict Mypy passes across `51`
  source files; frontend lint, strict TypeScript, and `7` Vitest tests pass (`1` opt-in contract test
  skipped); production Next build passes; `scripts/validate_demo.py` passes four layers, 152
  candidates, both golden budgets, and unchanged `1,811,120` credits; production Playwright passes
  the tutorial, map readiness, budget, site-context, source, and AI flow in `3.9s` after the
  20-site cache expansion.

## Cached Street View evidence is deterministic and screening-safe

- Exact-cache proof: the offline loader parses the legacy result plus 19 site-specific results and
  proves their 20 site IDs exactly equal the deterministic `$1M` portfolio. It rejects duplicate
  sites, incomplete jobs, malformed coordinates, dates, and segmentation values without making an
  external request.
- Metric proof: each dated front/back view preserves exact FortyGuard `tree`, `grass`, `sky`,
  `road`, `sidewalk`, and `building` percentages when present. Missing categories remain null.
  Aggregates use equal-weight observed means and publish the contributing-view count per metric.
- Confidence proof: versioned config scores usable views, imagery availability, cache-anchored image
  age, and segmentation completeness. All 20 real sites have one usable view and produce bounded,
  site-specific confidence scores from `0.688` to `0.875`.
- Intervention-screening proof: visible-sky and low-visible-tree context produce 20 distinct bounded
  shade-evidence scores from `0.234` to `0.592`, discounted by evidence confidence. Every record
  states that segmentation does not prove an unshaded stop, all-day shade, right-of-way, or
  construction feasibility. These values remain isolated from candidate ranking until the next
  checklist section.
- Artifact proof: `data/processed/pacoima_streetview_evidence.json` is a canonical, image-free
  `56,594`-byte artifact with SHA-256
  `97816ecd45f8934cd38762a748dd91ab96b7af459d2c05458d8fa3de1a642af5`. It embeds the config hash
  and source-cache hashes, and regenerates byte-for-byte from committed inputs.
- Automated proof: all `18` focused Street View tests pass, including missing views, malformed
  segmentation, stale imagery, view-order determinism, artifact regeneration, score bounds, and
  limitation retention. Full backend Pytest returns `69 passed`; Ruff passes; strict Mypy passes
  across `42` source files.

## Candidate confidence is evidence-specific and visible

- Candidate proof: the 20 exact-site Street View records replace the neutral `0.5` confidence with
  deterministic values from `0.688` to `0.875`; the other 132 candidates retain `0.5`. Feasibility
  remains the explicit unverified `0.5` because imagery does not establish right-of-way, utilities,
  safety, or constructability. Tests enforce the exact-site match and the neutral fallback.
- Rule proof: versioned candidate configuration names the exact-site confidence rule, while
  versioned intervention configuration declares the suitability inputs and feasibility gates for
  shade structures, tree canopy, and cool pavement. At that milestone cool pavement could not
  become operational until verified public paved geometry existed; the later authoritative-roadway
  section supersedes this historical gate with exact StreetsLA geometry.
- Traceability proof: every non-neutral candidate includes one Street View evidence record with
  image dates, usable-view count, all four component scores, derived confidence, artifact source,
  and the screening limitation. At least two verified sites have different scores for these
  explainable input differences.
- API/UI proof: `GET /v1/sites/{site_id}` returns the exact image-free frames, six named
  segmentation percentages, aggregate view coverage, confidence components, and shade-screening
  derivation when available, otherwise `null`. The selected-site drawer separates observed inputs
  from derived screening values, links the FortyGuard source, and keeps the field-verification
  limitation visible.
- Automated proof: full backend Pytest returns `74 passed`; Ruff passes; strict Mypy passes across
  `43` source files. Frontend lint, strict TypeScript, and all `7` Vitest tests pass (`1` opt-in
  contract test skipped); the production Next build completes successfully.

## FortyGuard exceedance has a measured live request

- Request proof: canonical hash
  `01b10110a2455dd1c8a33769eca3b1d9eb2ee1949d4e626cb4236a28907d7a58` represents the Pacoima
  7.763214 mi² AOI on 2024-07-15 at 100 m, `analytic_type=exceedance`, single-day filter, above
  30 °C. The request is aligned with the persistence threshold and spatial context.
- Credit proof: activity `e754402c-a9c8-4816-a981-786aa3e45f77` completed once. FortyGuard usage
  moved from `188,880` to `193,100`, an observed `4,220`-credit delta, leaving `1,806,900` above
  the `500,000` hard reserve.
- Cache proof: the durable terminal adapter record is `3,947,960` bytes, contains 2,001 GeoJSON
  features, omits the API key, and is tied to the same request hash and activity ID. A pre-submission
  journal prevents an uncertain request from being repeated. The validated, deterministic,
  secret-free dataset is committed as `data/processed/pacoima_fortyguard_exceedance.json`
  (`1,952,524` bytes), so demo use requires no raw cache or vendor access.
- Reserve proof: a workflow-level regression uses the observed `4,220`-credit heatmap cost with
  `504,219` credits remaining. The governor projects `499,999`, raises before submission, writes no
  request journal, and leaves the exceedance request absent from the ledger.
- Normalization proof: all 2,001 tiles carry real `exceedance_hours` and a deterministic
  winsorized `exceedance_score` in `[0,1]`; normalization metadata reports 2,001 valid values and
  zero missing values. The feature table records the exact exceedance-artifact SHA-256 and the
  2024-07-15 source-date limitation.
- Formula proof: every tile's modeled heat score is tested as exactly `0.40 × temperature_score +
  0.35 × persistence_score + 0.25 × exceedance_score`; deterministic candidate and optimizer tests
  pass after rebuilding downstream artifacts.
- Configuration proof: the three weights live in versioned `config/scoring.json`, are validated to
  sum to one, and are included in the feature table's scoring-config SHA-256. A functional test
  rebuilds all tiles with a temporary temperature-only preset, verifies every heat score follows
  that preset, and confirms scores differ from the committed default.
- Ranking sensitivity proof: against the former 50% temperature / 50% persistence baseline, 103 of
  152 candidate rank positions change and the maximum movement is 23 places. Portfolio membership
  replacement is 40% at `$250k`, 10% at `$500k`, and 0% at `$1M`; the test therefore classifies the
  smaller-budget effect as material at the predefined 10% decision threshold. This is a sensitivity
  result, not a causal claim, because exceedance is dated 2024-07-15 while active layers are 2026.
- API/UI proof: every site response exposes raw and normalized exceedance evidence. Methodology
  publishes the exact 40/35/25 heat weights, both analysis dates, 30 °C threshold/direction,
  canonical request hash, activity ID, artifact SHA-256, measured credit delta, FortyGuard source
  link, and mixed-period limitation. The drawer shows historical exceedance beside heat and
  persistence, then repeats its score/weight and provenance in progressively disclosed details.

## FortyGuard time-of-measure request support is contract-pinned

- Documentation proof: FortyGuard's Create Heatmap contract was rechecked on 2026-08-24. It defines
  `time_of_measure` on `POST /v1/heatmap` as the UTC hour (0–23) when peak temperature occurs, with
  hour units; threshold and direction are ignored for this analytic.
- Adapter proof: an offline transport test pins the authenticated single-day, 100 m request and
  exact `analytic_type=time_of_measure` serialization without making a live vendor request.
- Live measurement proof: canonical request
  `393a609d34ae19d5124b911b0e2d94d6c59409976357519b301b88bc5da56991` completed once as activity
  `eaa617ad-07b3-47db-9094-faa26c8eeb79`. Usage moved from `193,100` to `197,320`, an observed
  `4,220`-credit delta, leaving `1,802,680` above the `500,000` reserve.
- Result proof: the cached terminal record is `3,938,405` bytes with 2,001 features and `hour`
  units; aggregate values span UTC hours 3 through 17. The committed secret-free measurement report
  is validated as a no-resubmission marker before environment or client initialization.
- Committed-cache proof: `data/processed/pacoima_fortyguard_time_of_measure.json` is a deterministic,
  typed `1,947,712`-byte artifact containing all 2,001 spatially aligned tiles, the exact activity,
  request hash, UTC timezone, analysis date, observed cost, and source metadata. All tile values are
  complete integer hours in `[0,23]`; the real result contains only hours 03:00 and 17:00.
- Tile/site proof: every normalized tile now stores `peak_heat_hour_utc`, and every site API option
  inherits that exact tile context. The feature table records the time-of-measure artifact SHA-256;
  tests assert all 2,001 values remain exactly `{3, 17}` and downstream candidate provenance is
  rebuilt byte-for-byte without changing the score formula.
- Explanation-only proof: the observed-heat evidence supplied to deterministic and optional LLM
  explanations includes the exact zero-padded UTC peak hour and labels it historical context. A
  regression asserts the statement says it is explanation-only and not used in scoring; optimizer
  tests continue to pass with no peak-hour coefficient or normalized feature.
- Claim-safety proof: the explanation regression requires the peak-hour evidence to state it is not
  used for pedestrian-activity inference and rejects the unsupported phrase `peak pedestrian`.
- API/UI proof: Methodology exposes the peak-hour date, UTC timezone, request hash, activity ID,
  artifact SHA-256, measured cost, source link, and claim limitation. The selected-site drawer shows
  the concise label `Peak heat observed around` with a zero-padded `HH:00 UTC` value and date; its
  expandable provenance repeats that this is not evidence of peak pedestrian volume.
- Automated proof: full backend Pytest returns `99 passed`; Ruff passes; strict Mypy passes across
  `73` source files. Frontend lint and strict TypeScript pass; all `7` UI tests pass (`1` opt-in
  contract test skipped), and the production Next.js build completes successfully.

## FortyGuard environmental parameters are runtime-confirmed

- Contract proof: FortyGuard's Environmental Parameters documentation was rechecked on 2026-08-24.
  The probe uses the documented single-hour shape: latitude, longitude, matching heatmap
  temperature, and `date_time` with filter type 1.
- Selection proof: the request targets `Van Nuys / Herrick`, the highest modeled-impact member of
  the deterministic `$1M` portfolio, at its exact site point and representative TCM tile value
  `35.9398 °C` for `2026-08-20 14:00`.
- Live proof: canonical request
  `99bbf0bca690ad39a776b24025870a6650fb245d592e66364c7d202477ca3d2b` completed once as activity
  `0bd748b2-88dd-498c-ae5d-7aac35f07f92`. Usage moved from `197,320` to `200,220`, leaving
  `1,799,780` credits above the `500,000` reserve.
- Cost proof: the balanced before/after counters establish an observed `2,900`-credit cost for this
  one-location, one-hour environmental request shape. A regression pins the activity, request hash,
  both counters, delta, and remaining balance; it does not extrapolate cost to other request shapes.
- Go/no-go proof: access is runtime-confirmed and the reserve governor authorizes a conservative
  10-request projection only for the identical point/hour shape. At `2,900` credits each, projected
  cost is `29,000`, leaving `1,770,780` credits—`1,270,780` above the hard reserve. The finalist
  workflow may continue with `N <= 10`; wider time ranges remain unmeasured and unauthorized.
- Evidence-selection proof: versioned `config/environmental_parameters.json` promotes exactly three
  fields that exist in the real response: apparent temperature, relative humidity, and clear-sky
  GHI. Typed validation rejects a fourth field, missing/duplicate approved metrics, and unknown
  config keys. The remaining vendor response stays cached but is not promoted into finalist evidence.
- Claim-safety proof: each promoted field has a planning use and explicit limitation. Apparent
  temperature and humidity are not converted into medical or individual-exposure claims; GHI keeps
  the neutral `vendor value` unit because the endpoint result schema does not publish a unit.
- Top-N execution proof: the deterministic `$1M` portfolio is ordered by modeled impact with
  candidate ID as the tie-breaker and sliced at the hard `N=10` cap. The set contains 10 unique site
  IDs; rank 1 reused the probe, and exactly nine new canonical requests were submitted.
- Batch credit proof: all nine new activities completed at `2,900` credits each, matching the
  `26,100` preflight projection exactly. Usage advanced from `200,220` to `226,320`, leaving
  `1,773,680`; all ten one-location/one-timestamp responses validate from the processed cache.
- Replay proof: once all ten artifacts exist and match their deterministic candidate/request hashes,
  the batch returns them before loading environment settings or constructing a FortyGuard client.
- Cache-completeness proof: tests require an exact one-to-one mapping between the 10 deterministic
  finalists and the 10 committed JSON artifacts. Every artifact validates its canonical request
  hash, unique completed activity, one timestamp/location result, balanced counters, and source URL;
  the files contain no `api_key` field. Writes use atomic `.part` replacement.
- Normalization proof: the 10 full responses are transformed into one typed, deterministic artifact
  containing only observed temperature, apparent temperature, relative humidity, clear-sky GHI,
  coordinates, vendor time metadata, request/activity IDs, and per-source SHA-256 hashes. No value is
  normalized to a score, imputed, or timezone-corrected.
- Reproducibility proof: rebuilding `data/processed/pacoima_environmental_evidence.json` from the 10
  committed source responses is byte-for-byte stable. Rank 1 preserves the real values `35.3 °C`,
  `24.3%`, and GHI vendor value `779.49`.
- Candidate/site proof: exactly 10 candidate records receive a typed `thermal_stress_context` by
  exact `site_id`; all other candidates expose `null`. The candidate artifact hashes the normalized
  environmental input, and the same field flows through candidate-list and selected-site API
  schemas without a separate runtime lookup.
- Scoring isolation proof: the context is a nullable evidence field only. Candidate benefit,
  feasibility, confidence, objective coefficients, and deterministic portfolio code are unchanged.
- Medical-claim guard proof: the strict thermal-context schema exposes only raw contextual values
  and rejects an injected `medical_risk_score` as an extra field. Tests also reject any normalized
  environmental field name containing `score` or `risk`; limitations explicitly state that the
  evidence is not a medical-risk classification or individual health-effect estimate.
- Confidence proof: every finalist context computes a separate categorical `source_complete`
  assessment only after all 3 configured fields, exact request/activity IDs, and source artifact
  validate. Its basis and limitation travel with candidate/site responses. It is not a probability,
  accuracy claim, medical confidence, or intervention-outcome confidence.
- Optimizer isolation proof: environmental source completeness does not modify the existing
  feasibility/confidence scalars. Full optimizer regressions preserve the deterministic portfolios;
  this avoids treating a complete modeled response as proof that a site is constructible.
- UI acceptance proof: a selected finalist now shows a compact `Point thermal context` block with
  apparent temperature, humidity, GHI vendor value, observation date, vendor timezone, exact
  coordinates, source-completeness status, FortyGuard documentation link, and medical/outcome
  limitation. Sites outside the finalist set omit the block instead of implying missing live data.
- Live visual proof: Chrome DevTools MCP rendered the selected Van Nuys / Herrick finalist at
  1920×1080. The point-thermal block remained legible beside the map and displayed `35.30 °C`,
  `24.3%`, `779.49 vendor value`, `Source complete · 3 of 3`, date/timezone, coordinates, source
  link, and limitation. Console inspection found only the already-tolerated upstream basemap-tile
  `502` responses; no application/runtime error appeared.
- Cache proof: `data/processed/fortyguard_env_params_probe.json` validates the exact one-location,
  one-timestamp response, request, result, source, limitations, and balanced credit counters without
  containing the API key. Re-running the workflow returns this report before initializing a client.

## Intervention-value factors are bounded

- Contract proof: `InterventionValueFactors` validates priority, intervention suitability,
  feasibility, and confidence as finite values in `[0,1]`; the candidate schema reuses the same
  unit-interval type for every existing derived decision score.
- Calculation proof: the modeled-benefit product is deterministic and remains in `[0,1]`.
  Parameterized tests reject negative, above-one, infinite, and NaN values for every factor and
  cover both exact product boundaries.
- CP-SAT determinism proof: the optimizer sorts candidates by stable ID, integer-scales the
  objective, applies a stable ID tie break and fixed decision strategy, and runs one worker with
  seed `0`. The preset regression returns identical optimal portfolios when candidate input order
  is reversed (`1 passed`).
- AI isolation proof: an AST-based architecture regression inspects feature generation, candidate
  generation, intervention-value calculation, and optimization. It rejects imports of the
  explanation service or LLM/network-provider libraries, keeping optional AI downstream and
  explanation-only.
- Constraint-preservation proof: focused regressions cover all budget presets, assert total cost
  never exceeds budget, reject selecting two interventions at one site, and verify every one of the
  152 committed candidates against its intervention catalog eligibility rules (`3 passed`).
- Value-explanation proof: every candidate now serializes the exact four-factor formula, priority,
  intervention suitability, feasibility, confidence, final modeled-benefit product, suitability
  basis, and claim-safe limitation. Exact-site shade suitability uses the mean of available
  normalized open-sky/low-tree context; tree suitability uses normalized low-tree context; missing
  exact-site evidence uses the versioned neutral `0.5` fallback.
- Consumer proof: CP-SAT, template/optional-AI explanations, and the browser all read the same
  validated `modeled_benefit_score`, while `benefit_score` remains explicitly the underlying tile
  priority for backward-safe provenance.
- Automated proof: the candidate artifact rebuild is byte-for-byte reproducible; 24 focused
  backend tests pass; Ruff and Mypy pass across 76 source files; frontend lint and strict types
  pass; Vitest passes 7 tests with 1 opt-in test skipped; and the production Next build succeeds.
- Intervention-aware portfolio regression: every configured budget is solved twice, once with the
  committed candidate order and once reversed. Results are identical, optimal, within budget, and
  site-exclusive after suitability enters the objective.
- Intervention-evidence selection proof: a controlled optimizer regression holds priority (`0.8`),
  cost (`$50,000`), feasibility (`1.0`), and confidence (`1.0`) equal for two distinct sites. With
  one available slot, swapping only their suitability evidence (`0.9` versus `0.1`) swaps the
  selected site; the full optimizer test module passes all 4 tests.

## Authoritative Pacoima roadway geometry

- Acquisition proof: `scripts/acquire_roadway_geometry.py` queries the City of Los Angeles
  `Street_Information/MapServer/36` Streets (Centerline) layer using the committed Pacoima AOI
  envelope, requests WGS84 GeoJSON, and follows the service's 1,000-record pagination boundary.
- Completeness proof: a count query reported 1,913 intersecting centerlines; the committed
  `data/processed/pacoima_street_centerlines.geojson` contains exactly 1,913 unique, ordered
  service `AutoID` records and validates every geometry as a LineString or MultiLineString.
- Reproducibility proof: the acquisition sorts by the service-declared object ID, validates each
  page through strict typed schemas, writes atomically, and its committed artifact matches the
  canonical serializer byte-for-byte. Both focused tests, Ruff, and Mypy pass.
- Provenance proof: `data/sources.json` now names the City of Los Angeles Bureau of Engineering /
  GIS Mapping Division via GeoHub, the exact MapServer layer, retrieval date `2026-08-25`, City
  usage terms, retained source-field meanings, source/output CRS, AOI query rule, `AutoID`
  pagination, acquisition script, committed artifact, and 1,913-record count. It explicitly warns
  that centerlines do not prove width, ownership, paved material/condition, or constructability.
  The typed registry tests require this provenance and pass with the geometry tests (`6 passed`).
- Pavement-eligibility proof: the separate City Bureau of Street Services `Pavement Condition`
  layer contributed 1,703 dated segments with direct geometry, nonempty published surface codes,
  positive widths, and PCI values/categories. Candidate generation clips those lines to the exact
  Pacoima boundary, assigns intersecting verified heat tiles, retains the longest eligible segment
  per representative tile, and takes the 20 highest-priority tiles with stable asset-ID ties.
- Candidate proof: the canonical artifact now contains 172 candidates: 111 shade structures, 41
  tree-canopy sites, and exactly 20 cool-pavement corridors on 20 distinct official pavement
  assets/tiles. Each pavement record cites the exact source artifact and preserves surface codes
  without inventing definitions; suitability, feasibility, and confidence remain neutral pending
  product, field, and safety review.
- Automated proof: 24 focused acquisition/source/candidate/optimizer/API tests pass; the artifact
  rebuild is byte-for-byte stable; Ruff and Mypy pass across 79 source files; frontend strict types,
  ESLint, and all 7 active Vitest tests pass.
- Safety-gate proof: every cool-pavement candidate now carries the unresolved requirements for
  surface condition, wet traction, glare, drainage, pedestrian radiant exposure, and product
  compatibility. A catalog regression requires all six gates, while candidate tests require the
  same wording on each of the 20 serialized options; 13 focused tests pass and the rebuilt
  candidate artifact remains byte-for-byte reproducible.
- Satellite capability proof: exactly one governed 100 m `/v1/satellite` request was submitted for
  the deterministic top pavement corridor (`cool_pavement:pavement:21486`, tile `1355`) using the
  active heatmap date/hour. Activity `54e55cc7-c2be-46bf-866f-4c663c1b2dad` completed and is cached
  under canonical request hash `839afb7ccdcf43302459c9a6cadbc9372b3d8fb0242f75061df8278f636ea6a7`.
- Material-evidence proof: the 2026 satellite result reports `59.41%` `road, route` and `8.39%`
  `sidewalk, pavement` at the exact probe point, alongside building/vegetation context. This adds
  dated overhead surface coverage distinct from the City's administrative pavement line while
  remaining explicitly insufficient for ownership, condition, traction, glare, drainage, or
  product compatibility.
- Credit-safety proof: usage was queried before and after the same activity, moving from `226,320`
  to `240,720` credits and leaving `1,759,280`, safely above the `500,000` hard reserve. The journal,
  request cache, and ledger show one submission; subsequent runs poll/reuse that activity.
- Satellite unit-cost measurement: the observed delta for this exact one-point, single-hour,
  100 m request shape is `14,400` credits. It is a measured runtime cost, not a published price or
  a generalized estimate for other coordinates, dates, granularities, or batch sizes.
- Finalist-enrichment proof: the full 527 KB probe response is normalized into a compact,
  image-free `pacoima_satellite_evidence.json` record containing exact point/tile identity, image
  year/dimensions, seven published class percentages, the `67.80%` combined road-route plus
  sidewalk-pavement context, request/activity provenance, cost, source, and limitations.
- Scope-isolation proof: exactly one of 20 cool-pavement candidates—asset `21486`, the deterministic
  top pavement option—receives `satellite_surface_context` and a traceable evidence record. The
  other 19 remain `null`; no shade/tree candidate is enriched, and suitability, feasibility,
  confidence, priority, and optimizer code are unchanged.
- No-satellite fallback proof: a regression build with the optional satellite artifact path absent
  still produces all 20 cool-pavement candidates from the authoritative StreetsLA pavement geometry.
  The optional source is omitted, every satellite context remains `null`, and no live request occurs.
- Operational-family proof: all 20 pavement options receive data-level suitability `1.0` only after
  passing the versioned exact StreetsLA geometry, nonempty surface-code, positive-width, and PCI
  eligibility rule. Feasibility and confidence remain neutral `0.5`, preserving every unresolved
  field and engineering gate. The deterministic optimizer selects five cool-pavement options at the
  supported `$5,000,000` maximum budget; 19 focused candidate/optimizer/API tests pass.
- Conditional-removal decision: removal is not triggered because authoritative geometry supports 20
  candidates and the supported optimizer range demonstrably selects the family. The catalog and UI
  may therefore retain cool pavement while continuing to disclose its unresolved safety gates.
- Scenario-contract proof: `GET /v1/pilot` now advertises the ordered `balanced`, `heat_first`,
  `equity_first`, and `exposure_first` enum values plus a balanced default. `POST /v1/optimize`
  accepts the same typed selector, and the TypeScript client/Zod boundary shares those exact values.
  Seven API tests, frontend strict type generation, and all seven active frontend tests pass.
- Zero-cost scenario proof: `config/scenarios.json` versions the four required weight sets. The
  optimizer recomputes priority from the committed tile heat, exposure, vulnerability, and cooling-
  opportunity scores, then applies the unchanged suitability/feasibility/confidence factors and
  CP-SAT constraints. A 500k heat-first request returns different selected IDs from balanced with no
  FortyGuard path involved; 13 focused API/optimizer tests and frontend checks pass.
- Robustness-computation proof: each optimize API response now solves all four cached scenarios and
  annotates every site in the active portfolio with the exact selected preset IDs, numerator,
  denominator `4`, and `robustness_score = presets_selected / presets_tested`. A regression confirms
  the ratio and includes sites below `1.0`; 14 focused backend and 7 active frontend tests pass.
- Robustness-label proof: every ranked recommendation with a matching API record now shows concise
  audit copy in the existing metadata row, for example `Selected in 4/4 planning scenarios`. The
  label uses the returned numerator/denominator rather than recalculating in the browser. Frontend
  typecheck, zero-warning ESLint, and all seven active component tests pass.
- Interpretation-guard proof: the versioned optimizer config and every portfolio response state that
  robustness is selection frequency across planning-weight scenarios, not statistical confidence,
  outcome certainty, or probability. The recommendation rail repeats the concise visible warning;
  14 focused backend tests and all frontend quality gates pass.
- Four-preset regression proof: the optimizer test suite asserts each exact required weight vector,
  complete ordered catalog membership, stable results under reversed candidate input, the echoed
  active preset, and budget feasibility for balanced, heat-first, equity-first, and exposure-first.
  All eight optimizer tests pass with Ruff and Mypy clean.
- Pre-UI Impeccable proof: the required context loader resolved the full `PRODUCT.md` and `DESIGN.md`,
  the product-register guidance was applied, and the scenario golden path was reviewed before the
  next control change. The resulting constraint is to extend the existing budget overlay with a
  familiar compact selector and active weights, preserving the map-first hierarchy. The executable
  golden-path validator passes with four layers, 172 candidates, both demo budgets, and credits
  unchanged at `1,759,280` remaining.
- Scenario-control proof: the existing investment overlay now contains one keyboard-native planning-
  priority select with all four presets and a compact `H/E/V/O` active-weight readout. Changing it
  posts the current budget plus preset to the local optimizer, updates portfolio/site/robustness state,
  preserves the preset across budget changes and refresh reloads, and makes no FortyGuard request.
- Explanation-consistency proof: explanation requests and cache keys include the active preset;
  deterministic summaries recompute the displayed priority and modeled impact from that scenario's
  weights. Thirteen focused backend tests, frontend strict types, zero-warning lint, and all eight
  active UI tests pass.
- Drawer-completeness proof: the selected-site drawer now presents dated FortyGuard heat,
  persistence, exceedance and peak timing; optional point environmental context; a direct control
  into cached original/segmented Street View; scenario priority, intervention evidence,
  feasibility, confidence and robustness; local cost basis/range; sources and limitations.
- Scenario-score proof: portfolio responses carry the selected candidates' exact scenario priority
  and modeled impact scores. Both the ranked rail and drawer use those returned values, preventing
  balanced-score remnants after a preset change. Fifteen focused backend tests and all eight active
  UI tests pass with both language toolchains clean.
- Evidence-hierarchy proof: the drawer now explicitly labels the price/intervention block as a
  `Planning assumption`, the optimizer factors as `Derived screening scores`, and the dated vendor
  and public inputs as `Observed and published evidence`. Existing Street View subsections retain
  separate observed segmentation and derived-screening headings. Frontend typecheck, lint, and all
  eight active component tests pass.
- Semantic-indicator proof: restrained, text-complete indicators now label `Verified evidence`,
  `Modeled`, `Planning assumption`, and `Field verification required`. Teal, neutral, and amber
  styling reinforce meaning but the literal text carries it for color-independent comprehension.
  Frontend typecheck, zero-warning lint, and all eight active component tests pass.
- Map-hierarchy proof: the desktop workspace retains fixed `21rem` and `23.5rem` analytical rails
  around the sole fluid `minmax(28rem, 1fr)` map column. At narrower breakpoints the map remains the
  first workspace surface before recommendation and evidence content. The eight-test golden UI
  regression confirms the interactive map region remains present and primary.
- Zero-credit replan proof: the budget overlay's live status now announces the exact result as
  `N sites · 0 FortyGuard credits`, while the persistent portfolio summary independently displays
  `FortyGuard credits: 0`. The budget regression still verifies that re-optimization makes no
  request to any FortyGuard URL; strict typecheck, zero-warning lint, and all eight active frontend
  tests pass.
- Post-implementation Impeccable proof: the completed UI was re-audited against the loaded product
  context and Impeccable guidance. The review confirms the map remains the sole fluid hero, the new
  planning control uses a compact native select, evidence semantics are text-complete rather than
  color-dependent, and existing responsive/reduced-motion/focus rules remain intact. It also found
  the tour-dialog keyboard lifecycle as a concrete accessibility follow-up for the next task.
- Accessibility and resilience proof: the tour now receives initial focus, contains forward and
  reverse Tab navigation, closes on Escape, and restores the invoking control. Source order now
  places the map first for narrow-screen and keyboard reading while explicit desktop grid areas
  preserve the recommendation/map/evidence layout. Component regressions verify map-first order,
  the no-segmentation empty state, visible initial-load failure plus Retry recovery, and retained
  operation-error behavior. All 11 active UI tests, strict TypeScript, and zero-warning lint pass.
- Product-contract audit proof: `PRODUCT.md` now matches the implemented four scoring presets,
  four-scenario robustness semantics, `$50k`–`$5M` local budget range, zero-credit replanning,
  bounded optional evidence, AI explanation-only role, exact StreetsLA pavement eligibility, and
  complete-refresh behavior. A direct config/artifact check confirms three presets at
  `$250k/$500k/$1M`, four scoring scenarios, 172 total candidates, and 20 pavement candidates.
- Architecture audit proof: `ARCHITECTURE.md` now documents the typed budget/preset optimizer
  boundary, active scenario scores and robustness output, protected live-refresh endpoint and full
  workspace reload, exact StreetsLA pavement dependency, bounded `20/10/1` street/environmental/
  satellite enrichments, cached image serving, and OpenRouter explanation fallback using the
  configured `stealth/ox-alpha` model. All 21 decision API, optimizer, and explanation tests pass.
- README audit proof: the professional project entry point now documents four planning scenarios,
  bounded optional evidence, StreetsLA pavement screening, `openrouter` mode, refresh status,
  robustness limitations, and the current artifact inventory. Every referenced local file exists;
  direct artifact parsing confirms 172 candidates (`111` shade, `41` tree, `20` pavement) and
  `20/10/1` street/environmental/satellite evidence records.
- Automated proof: the normalized artifact excludes original/mask image payloads, remains under
  5 KB, and rebuilds byte-for-byte. Twenty focused tests, Ruff, Mypy, strict TypeScript, canonical
  candidate rebuild, and all 11 active frontend tests pass.

# EVIDENCE

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
- Scoring/claim proof: benefit equals the frozen tile priority score and equity equals its
  vulnerability score. Feasibility and confidence use the disclosed neutral `0.5` unverified
  screening scalar, which is explicitly not a probability or measured effect; no intervention
  effect multiplier or temperature forecast is invented.
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

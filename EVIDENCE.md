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

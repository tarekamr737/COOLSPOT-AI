# ARCHITECTURE.md

## Goal
A small, deterministic, deployable geospatial decision-support system. Optimize for hackathon reliability, auditability, low FortyGuard credit use, and low coding-agent token use.

## Stack
- Web: Next.js + TypeScript, latest stable, strict mode.
- UI/UX: **Impeccable skill is mandatory** for all visual/interaction work.
- Map: MapLibre GL JS (no vendor lock-in required for core logic).
- API: Python + FastAPI + Pydantic.
- Geospatial: GeoPandas + Shapely + PyProj.
- Optimization: Google OR-Tools CP-SAT.
- Data: committed GeoJSON/GeoParquet/JSON fixtures for MVP.
- Tests: Pytest + frontend unit tests + Playwright golden-path E2E.
- Deployment: Vercel for web; Dockerized FastAPI on a container host. Keep host-specific config minimal.

A database is intentionally deferred. Add PostGIS only if file-backed data becomes a measured blocker.

## Repository
```text
.
├── AGENTS.md
├── PRODUCT.md
├── ARCHITECTURE.md
├── TASKS.md
├── web/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── tests/
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   ├── services/
│   │   │   ├── fortyguard.py
│   │   │   ├── credits.py
│   │   │   ├── public_data.py
│   │   │   ├── scoring.py
│   │   │   ├── candidates.py
│   │   │   ├── optimizer.py
│   │   │   └── explanations.py
│   │   └── data_access.py
│   └── tests/
├── data/
│   ├── raw/          # gitignored live downloads except tiny licensed fixtures
│   ├── processed/    # demo-ready datasets
│   ├── fixtures/     # sanitized API fixtures
│   └── sources.json
├── scripts/
│   ├── build_pilot.py
│   ├── refresh_fortyguard.py
│   └── validate_demo.py
└── .env.example
```

## Environment
```text
FORTYGUARD_API_KEY=
FORTYGUARD_LIVE=0
FORTYGUARD_CREDIT_TOTAL=2000000
FORTYGUARD_CREDIT_RESERVE=500000
NEXT_PUBLIC_API_BASE_URL=
EXPLANATION_MODE=template
```

Never prefix the FortyGuard key with `NEXT_PUBLIC_`.

## Startup modes
### Demo
`FORTYGUARD_LIVE=0`
- serves committed processed data/fixtures,
- cannot submit FortyGuard jobs,
- is the default for dev, CI, and final demo fallback.

### Live refresh
`FORTYGUARD_LIVE=1`
- server-side only,
- requires explicit refresh command,
- credit governor checks reserve,
- writes raw response + request metadata before preprocessing.

## FortyGuard adapter
Expose a narrow interface:
```python
submit_heatmap(request) -> ActivityId
submit_env_params(request) -> ActivityId
submit_satellite(request) -> ActivityId
submit_streetview(request) -> ActivityId
get_status(activity_id) -> ActivityStatus
```

Do not leak vendor response shapes past the adapter. Convert completed results into internal Pydantic models.

### Async behavior
- Persist `activity_id` immediately.
- Poll with bounded exponential backoff + jitter.
- Resume polling known activities after restart.
- Do not resubmit an in-flight request.
- Cache completed response by canonical request SHA-256.

## Credit governor
FortyGuard's public docs describe credits but do not provide a universal fixed cost per request, so learn actual hackathon-key cost empirically.

Persist a ledger:
```text
timestamp
request_hash
endpoint
request_summary
usage_before
usage_after
observed_cost
activity_id
status
```

Algorithm:
1. Get current usage before first live call.
2. Send one minimal valid request.
3. Poll to completion.
4. Get usage again.
5. Store observed delta.
6. Before batching, estimate total using conservative observed cost.
7. Abort if projected remaining `< 500,000`.
8. Never submit a request whose hash already has a successful cached result.

Treat the user's 2,000,000 allocation as the authoritative project budget, but probe endpoint capability separately because public plan access and credit count are different concerns.

## Pilot boundary
Acquire an authoritative Pacoima boundary if practical; otherwise document a simplified MVP analysis polygon.
- CRS for storage/API: WGS84 (`EPSG:4326`).
- Project to an appropriate local CRS before area calculations.
- Validate closed Polygon / FeatureCollection format expected by FortyGuard.
- Hard fail if AOI >=10 mi².
- Prefer target <=9.5 mi² to leave tolerance.
- Commit result to `data/processed/pacoima_aoi.geojson`.

## Heat acquisition
First successful real dataset:
- AOI: Pacoima.
- Granularity: `100m`.
- Analysis: `tcm`.
- Historical hot-day/time window chosen and recorded in metadata.

Second:
- same AOI/date context,
- `persistence`,
- threshold stored in config with rationale.

Only add `exceedance` if it materially changes ranking or demo explanation.

Do not spend credits exploring many dates. Use one defensible hot period for the MVP and make refresh a post-MVP feature.

## Capability probe
Do not spend multiple calls testing Premium features.
- Read usage/account metadata if available.
- Attempt at most one small call per optional endpoint only when needed.
- A 403/plan error disables that feature cleanly.
- Satellite/street-view enrich only a small top-N site set.

## Public-data pipeline
One-time ingestion -> cached processed outputs.

1. LA Metro:
   - GTFS stops/routes.
   - published bus-stop need/ridership/equity dataset where available.
2. Census ACS:
   - fetch only required variables for intersecting tracts/block groups.
3. POIs:
   - authoritative city/LAUSD datasets when easy; otherwise OSM snapshot.
4. Optional canopy/land-cover:
   - only if source/licensing is clear.

Normalize to WGS84 and clip to pilot AOI.

## Spatial join
Base table is FortyGuard grid tile:
```text
tile_id
geometry
temperature
persistence_hours
exceedance_hours?
heat_score
population_proxy
transit_exposure
poi_exposure
vulnerability_score
cooling_opportunity
priority_score
```

Spatial operations happen in Python preprocessing, not in the browser.

## Normalization
Use robust min-max/winsorized normalization with deterministic config.
- Handle missing values explicitly.
- Store raw value + normalized value.
- Never normalize across hidden future data in a way that changes cached demo results.

Default:
```text
priority =
0.40 * heat
+ 0.30 * exposure
+ 0.20 * vulnerability
+ 0.10 * opportunity
```

## Candidate generation
Generate candidates only where a supported intervention is compatible.

Examples:
- transit stop + high heat + low shade evidence -> shade structure
- school/park/corridor + low canopy opportunity -> trees
- public paved area/corridor + surface opportunity -> cool pavement

Each candidate:
```text
id
site_id
tile_id
intervention_type
planning_cost
benefit_score
equity_score
feasibility_score
confidence
evidence[]
geometry
```

Use conservative planning-cost assumptions from versioned `data/processed/interventions.json`.

## Optimizer
CP-SAT variables: `x[candidate] ∈ {0,1}`.

Maximize integer-scaled:
```text
candidate_value =
priority_score
* intervention_modifier
* feasibility_score
* confidence
```

Subject to:
```text
Σ planning_cost * x <= budget
Σ x for same site <= 1
incompatible candidate => x = 0
optional equity constraint
```

Return:
- selected candidate IDs,
- total cost,
- unused budget,
- total modeled impact score,
- category counts,
- equity summary.

No LLM in this path.

## API contract
Minimal endpoints:
```text
GET  /health
GET  /v1/pilot
GET  /v1/layers/{layer}
GET  /v1/candidates
POST /v1/optimize
GET  /v1/sites/{site_id}
GET  /v1/methodology
GET  /v1/data-status
```

`POST /v1/optimize` accepts only scenario inputs; it must never call FortyGuard.

Admin/live refresh should be a CLI script for MVP, not a public endpoint.

## Explanations
Default deterministic template generated from site evidence.

Optional `EXPLANATION_MODE=llm`:
- input is one compact JSON object for selected site,
- include only cited evidence already in system,
- output schema: `summary`, `why_selected`, `limitations`,
- temperature/cost/effect numbers must be copied from input, never generated,
- cache by site + scenario hash.

## Frontend data flow
- Fetch pilot metadata and layers once.
- Map layers are client-rendered GeoJSON.
- Budget change -> call `/v1/optimize` only.
- Selecting site -> fetch/display site evidence.
- Never fetch raw FortyGuard Base64 imagery until a user opens an enriched site.

## Impeccable UI implementation
Before UI code:
1. Invoke/read Impeccable skill.
2. Have it define information hierarchy and map interaction.
3. Implement its recommendations using project components.
4. Re-run Impeccable review after golden path exists.
5. Fix accessibility/responsiveness issues it identifies.

If skill is unavailable, mark UI tasks blocked rather than inventing a substitute.

## Reliability
- Server timeouts on external calls.
- Retry only safe GET/status checks automatically.
- No unbounded loops.
- Structured logging without secrets/signed URLs.
- Keep fixture sizes small enough for repo/deployment.
- Graceful map error state if basemap fails; core recommendations remain readable.

## Security
- Secret key server-only.
- CORS allowlist in deployed API.
- Pydantic input validation.
- No arbitrary URL fetching from user input.
- No user-auth scope for MVP.
- Source/signed download URLs are not logged if sensitive/temporary.

## Tests
### Unit
- GeoJSON/AOI area validation.
- score normalization.
- missing-data behavior.
- candidate compatibility.
- optimizer budget/site constraints.
- credit reserve/caching logic.

### Integration
- FortyGuard fixture parsing.
- public-data preprocessing fixtures.
- API response schemas.

### E2E
Golden path:
`load Pacoima -> toggle layer -> set $500k -> inspect result -> set $1M -> inspect site -> methodology`.

Assert no FortyGuard request occurs during E2E.

## Deployment
- Build frontend with API base URL env.
- Build API as Docker image.
- Run `scripts/validate_demo.py` against deployed API.
- Run Playwright golden path against deployed web.
- Keep demo-mode processed data available so live vendor/API failure cannot kill judging.

## Production path after hackathon
Add PostGIS, scheduled refresh jobs, city asset/ownership/utility constraints, calibrated intervention models, real procurement costs, auth/audit logs, and city-specific engineering review. None are required to win the MVP demo.

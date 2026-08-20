# PRODUCT.md

## COOLSPOT AI

**One-line product:** Give COOLSPOT an urban cooling budget; it identifies persistent heat-exposure hotspots and selects the most defensible portfolio of cooling interventions.

## User
Primary: municipal climate-resilience / public-works planner.
Secondary: transit, parks, sustainability, and environmental-justice teams.

## Problem
Cities can already see that heat is uneven. The harder operational question is: **with a fixed budget, where should cooling money go first, and why?**

COOLSPOT converts temperature intelligence + human exposure + vulnerability + intervention feasibility into an auditable investment decision.

## MVP pilot: Pacoima, Los Angeles, California
Use the **Pacoima neighborhood** as the single pilot.

Why:
- Published planning material describes Pacoima as about **7.14 mi²**, fitting within FortyGuard's documented 10 mi² Basic/Startup heatmap limit.
- Peer-reviewed work describes Pacoima as one of Los Angeles County's highly heat-impacted/vulnerable areas and reports substantial heat-trapping impervious cover.
- Pacoima has already hosted real cool-pavement research, giving the pitch a real intervention context rather than a hypothetical one.
- LA Metro publishes unusually useful bus-stop prioritization, ridership, and equity resources.
- The pilot contains transit stops, schools, parks, civic facilities, homes, and industrial land—good variety for site-level recommendations.

The committed AOI must be validated programmatically before any live FortyGuard call. If an authoritative boundary cannot be obtained quickly, create a documented simplified polygon covering Pacoima with area <9.5 mi² and label it `MVP analysis boundary`.

## Golden demo
1. User opens Pacoima.
2. Map shows real cached FortyGuard heat data and ranked hotspots.
3. User toggles Heat / Persistence / Exposure / Vulnerability.
4. User sets a budget, e.g. `$500k`.
5. Optimizer selects a portfolio of candidate interventions.
6. User moves budget to `$1M`; portfolio updates instantly **without another FortyGuard call**.
7. User clicks a site and sees:
   - observed/modelled heat evidence,
   - exposure/vulnerability evidence,
   - recommended intervention,
   - planning cost assumption/range,
   - modeled impact score,
   - confidence/limitations,
   - source links.
8. User asks “Why this site?” and gets a grounded explanation from structured evidence.

## MVP inputs

### FortyGuard
Required:
- `POST /v1/heatmap`, `analytic_type=tcm`
- `POST /v1/heatmap`, `analytic_type=persistence`

Useful if evidence justifies:
- `analytic_type=exceedance`
- `/v1/env_params` for a few top sites

Optional only after access probe:
- `/v1/satellite`
- `/v1/streetview`
- `/v1/heat_intelligence`

Use async `activity_id` + status polling and persist completed results.

### Public data
Prefer cached authoritative datasets:
- LA Metro static GTFS: transit stops/routes.
- LA Metro Bus Stop Hub: prioritization/ridership/equity data where downloadable/usable.
- US Census ACS 5-year: population and vulnerability variables.
- City/County open data or OpenStreetMap: schools, parks, libraries, civic facilities.
- Optional authoritative tree-canopy/land-cover layer if licensing and retrieval are straightforward.

Every dataset gets `source`, `retrieved_at`, and `license_notes`.

## Core unit of analysis
Use FortyGuard heatmap tiles as the base spatial grid. Join nearby POIs/exposure/vulnerability features to those tiles.

Do not pretend a tile is a person or parcel.

## Scores
All component scores normalized to `[0,1]`.

Default transparent weights:
- Heat severity: `0.40`
- Human exposure: `0.30`
- Vulnerability: `0.20`
- Cooling opportunity: `0.10`

`priority_score = weighted sum`

Weights live in config and can be changed by scenario presets. UI must show the active weighting preset.

### Heat severity
Derived from available FortyGuard signals:
- temperature intensity,
- persistence above threshold,
- optional exceedance.

### Human exposure
Evidence may include:
- published stop ridership,
- proximity to transit,
- schools/parks/civic destinations,
- resident population.

Do not convert proximity into fake footfall.

### Vulnerability
Use a small, explainable ACS feature set (example: older adults, children, poverty/low income, households without vehicles) after validating fields and denominators.

### Cooling opportunity
Derived from available land-cover/amenity evidence:
- low canopy/vegetation,
- exposed transit stop,
- large paved surface,
- public/civic site,
- intervention-site compatibility.

## Intervention catalog
MVP supports three intervention families:

1. **Shade structure**
   - Best for: exposed transit stops / pedestrian waiting areas.
2. **Tree canopy**
   - Best for: suitable public corridors, schools, parks.
3. **Cool pavement**
   - Best for: suitable large paved public surfaces/corridors.

Each intervention config contains:
- applicability rules,
- planning cost estimate/range,
- evidence-backed effect range or qualitative benefit,
- evidence source,
- uncertainty,
- lifespan/maintenance note if known.

Costs are **planning assumptions**, not contractor quotes.

## Candidate recommendation
A candidate is:
`site + intervention + cost + modeled_benefit + feasibility + confidence + evidence`

For MVP, mutually exclusive interventions at the same site cannot both be selected.

## Optimization
Given `budget`, select candidates maximizing total modeled benefit subject to:
- `sum(cost) <= budget`
- at most one intervention per site
- intervention/site compatibility
- optional minimum equity share if enabled

The objective is a **modeled impact score**, not guaranteed temperature reduction or lives saved.

## Budget scenarios
Provide presets:
- `$250k`
- `$500k`
- `$1M`
- Custom within configured bounds

Re-optimization uses precomputed features and candidates. Moving the slider must not consume FortyGuard credits.

## Required UI surfaces
All visual/UX work is implemented through the **Impeccable skill**:
- primary interactive map,
- layer controls,
- budget/scenario control,
- KPI summary,
- ranked recommendation list,
- site evidence drawer,
- methodology/limitations panel,
- data/credit freshness indicator.

Do not add decorative pages that do not help the golden demo.

## KPI language
Allowed:
- modeled priority score,
- modeled impact score,
- high-priority tiles addressed,
- transit stops/schools/parks included,
- budget allocated,
- equity share of selected portfolio,
- data freshness,
- evidence confidence.

Avoid:
- “people saved,”
- “deaths prevented,”
- “exact °C reduction” unless reporting a cited study range for comparable conditions,
- “this bus stop is unshaded” unless directly evidenced.

## Real-vs-demo behavior
- `demo mode`: loads committed, real cached responses/data; zero external calls.
- `live refresh`: explicit server-side/admin action; credit-governed.
- UI always labels data date and whether it is cached/live.

## Non-goals for hackathon
- citywide California coverage,
- construction-ready engineering design,
- parcel ownership/utility conflict checks,
- exact microclimate simulation,
- procurement quotes,
- autonomous spending decisions,
- user accounts/payments,
- mobile-native app.

## Acceptance criteria
- Pacoima AOI area validation passes and is below 10 mi².
- At least one real successful FortyGuard heatmap + persistence dataset is cached.
- At least two public exposure/vulnerability sources are integrated.
- >=20 candidate sites are generated from real pilot data.
- Optimizer returns deterministic feasible portfolios for all budget presets.
- Changing budget does not trigger a FortyGuard request.
- Every selected intervention has traceable evidence and a disclosed cost assumption.
- No unsupported impact claim appears in UI/API.
- Demo works with network disconnected except for map basemap if not locally cached.
- Golden E2E path passes on deployed build.

## Research anchors
- FortyGuard docs: https://docs-api.fortyguard.com/
- FortyGuard limits: https://docs-api.fortyguard.com/docs/limitations
- Pacoima resilience plan: https://www.csun.edu/sites/default/files/Pacoima_Plan_English_Spreads_SP20.pdf
- Pacoima heat/exposure study: https://www.nature.com/articles/s44304-024-00053-4
- Pacoima cool-pavement field study: https://doi.org/10.1088/2515-7620/AD2A8E
- LA Climate Vulnerability Assessment: https://planning.lacity.gov/
- LA Metro Bus Stop Hub: https://busstophub.metro.net/resources/maps/
- LA Metro API: https://api.metro.net/

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

The committed official neighborhood AOI is validated programmatically at **7.763 mi²** before any
live FortyGuard call and is labeled as the analysis boundary. The separate `7.14 mi²` figure above
is contextual planning literature, not the geometry used by the application.

## Golden demo
1. User opens Pacoima.
2. Map shows real cached FortyGuard heat data and ranked hotspots.
3. User toggles Heat / Persistence / Exposure / Vulnerability.
4. User sets a budget, e.g. `$500k`.
5. Optimizer selects a portfolio of candidate interventions.
6. User moves budget to `$1M`; portfolio updates instantly **without another FortyGuard call**.
7. User changes the planning priority among Balanced, Heat-first, Equity-first, and Exposure-first;
   the deterministic portfolio and each site's four-scenario selection frequency update locally.
8. User clicks a site and sees:
   - observed/modelled heat evidence,
   - exposure/vulnerability evidence,
   - cached exact-site street segmentation where available,
   - optional point environmental context where collected,
   - recommended intervention,
   - planning cost assumption/range,
   - modeled impact score,
   - feasibility, confidence, scenario robustness, and limitations,
   - source links.
9. User asks “Why this site?” and gets a concise, source-linked explanation constrained to the
   selected site's structured evidence. AI explains; it never ranks or optimizes.

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
Satellite and Street View are bounded, cached evidence enrichments. Their absence must produce a
visible unavailable state and must not disable the deterministic core workflow. Heat Intelligence
remains outside the core dependency path.

### Public data
Prefer cached authoritative datasets:
- LA Metro static GTFS: transit stops/routes.
- LA Metro Bus Stop Hub: prioritization/ridership/equity data where downloadable/usable.
- US Census ACS 5-year: population and vulnerability variables.
- City/County open data or OpenStreetMap: schools, parks, libraries, civic facilities.
- StreetsLA Bureau of Street Services pavement-condition geometry for cool-pavement screening.
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

Weights live in versioned config and can be changed by four exact scenario presets:
- Balanced: `0.40 / 0.30 / 0.20 / 0.10`
- Heat-first: `0.50 / 0.25 / 0.15 / 0.10`
- Equity-first: `0.30 / 0.25 / 0.35 / 0.10`
- Exposure-first: `0.30 / 0.40 / 0.20 / 0.10`

The vectors are ordered heat / exposure / vulnerability / cooling opportunity. The UI shows the
active preset and weights. Scenario robustness is selection frequency across these four planning
weight sets; it is not statistical confidence, probability, or outcome certainty.

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
   - Best for: exact mapped StreetsLA pavement segments that pass the versioned data-level geometry
     rule. Surface condition, treatment area, ownership, product, safety, and construction
     feasibility still require field review.

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
The custom range is `$50k`–`$5M`; every completed local recalculation visibly reports
`0 FortyGuard credits`.

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
The evidence drawer must distinguish observed/published evidence, derived screening scores, and
planning assumptions with text-complete indicators. Color cannot carry those meanings alone.

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
- A completed refresh reloads layers, candidates, scores, recommendations, and the portfolio; it is
  not complete if only the map changes.

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
- The committed catalog contains 172 candidates from real pilot data, including 20 cool-pavement
  candidates grounded in exact StreetsLA pavement geometry.
- Optimizer returns deterministic feasible portfolios for all budget presets.
- Changing budget or scoring preset does not trigger a FortyGuard request and visibly reports zero
  credits consumed.
- Every selected intervention has traceable evidence and a disclosed cost assumption.
- Scenario robustness is disclosed as four-preset selection frequency and never as confidence.
- Missing optional Street View, satellite, or environmental evidence remains visibly unavailable;
  it is never silently replaced with fabricated evidence.
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

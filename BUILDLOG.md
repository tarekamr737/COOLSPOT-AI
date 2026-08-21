# BUILDLOG

## 2026-08-20

- Frontend smoke tests initially timed out while Vitest started its default forked worker on
  Windows. Configured a single worker-thread pool so the test command is reliable in this
  environment and CI without weakening test assertions.
- Selected the City of Los Angeles certified Pacoima Neighborhood Council polygon as the pilot
  AOI instead of inventing a simplified boundary. Its projected area is 7.763214 mi², so no
  clipping or geometry simplification was needed.
- The 2024 ACS API returned an HTML `Missing Key` page with HTTP 200 when no Census key was
  available. Switched to the official no-account table-based Summary File, streamed only LA
  County tract rows, and required schema validation before any downloaded response is promoted
  to the raw cache.
- FortyGuard's heatmap endpoint page documents `filter_type=4` for ranges up to one month, while
  its general limitations page lists only types 1–3. The adapter accepts type 4 only for heatmaps,
  keeps environmental/satellite requests to types 1–3, and the MVP will use types 1/3 until a
  single controlled runtime request confirms behavior.
- FortyGuard documentation names the usage endpoints but does not publish a stable response
  schema. The credit governor therefore consumes a validated absolute usage reading and does not
  invent vendor fields; runtime response mapping is deferred to the single controlled usage probe.
- The live usage endpoint rejected the documented header-style authentication shape with HTTP 422
  and required `api_key` in its JSON body. The adapter now uses that runtime contract over HTTPS,
  validates only the current-cycle credit counters, and never logs or caches the credential.
- The completed live heatmap contained a standard GeoJSON `id` on every feature, although the
  published example and original fixture omitted it. Strict validation caught the difference; the
  model and fixture now accept typed string/integer feature IDs, and polling resumed the original
  cached activity rather than resubmitting it.
- Used a one-hour 14:00 TCM layer and a same-date daily persistence layer on the identical 100 m
  grid. The 30 °C persistence threshold is a versioned, disclosed planning threshold—not a health
  cutoff—so it supports relative hotspot ranking without implying unsupported safety effects.
- Made no Premium/optional endpoint probes: the next core feature-table task is fully supported by
  cached TCM, persistence, Metro/POI, and ACS data. Optional access remains explicitly unconfirmed
  and fail-closed until a ranked-site dependency demonstrates incremental MVP value; this avoids
  spending credits merely to discover plan entitlements.
- The feature table treats ACS totals as area-weighted tract context, not apportioned tile counts,
  and uses published Metro ons+offs without assigning meanings to the retained DX/SA/SU prefixes.
  A 0/0 ACS vehicle-household denominator remains explicitly missing and its composite weight is
  redistributed across available vulnerability rates.
- FortyGuard's returned tiles missed two authoritative AOI-edge Metro points by 3.2 m and 14.6 m.
  Added a versioned 25 m nearest-tile tolerance and per-record proximity flags; all farther points
  would remain visibly unmatched rather than being silently snapped.

## 2026-08-21

- Kept intervention effects qualitative even where the Pacoima cool-pavement study reports numeric
  observations: transferring a study value into a candidate forecast would imply unsupported
  precision. The catalog retains the local study, its variability, and its transfer limits.
- Treated intervention prices as rounded portfolio-screening allowances with explicit units,
  ranges, exclusions, and source context. Shade/tree candidates may be screened from authoritative
  stop or public-site locations, while cool pavement remains ineligible until direct paved-surface
  evidence exists; no existing shade, canopy gap, or surface condition is inferred.
- Generated one candidate per authoritative compatible site and selected the highest-priority
  intersecting heat tile for polygon sites, avoiding duplicate candidates for large school/park
  geometries. Cool pavement remains at zero candidates rather than treating heat or POI proximity
  as evidence of a suitable paved surface.
- Assigned the same neutral `0.5` unverified feasibility/confidence scalar to both supported
  intervention families. This prevents unsupported intervention-effect differences from changing
  ranking while retaining the numeric fields required by the deterministic optimizer contract.
- Implemented CP-SAT with integer-scaled primary impact coefficients and a bounded candidate-ID
  secondary term: one primary integer unit dominates every possible tie-break contribution. The
  solver also sorts inputs, uses one worker/fixed seed/fixed search, and rejects any result not
  proven optimal, so caller order and parallel scheduling cannot alter the portfolio.
- Built every public decision route from schema-validated committed artifacts and cached those
  read-only loads in-process. Layer responses expose internal typed properties rather than vendor
  response shapes; optimization imports no live-refresh path, and data status labels the served
  mode as cached even if an administrator has separately enabled live refresh in the environment.
- Impeccable inferred the `product` register from the municipal planner workflow and drove a
  restrained, map-dominant civic-tech shell using the existing `DESIGN.md`. The documented
  project-local context loader was absent, so the installed global loader was used against the
  repo. In-app browser control was not callable; semantic DOM, responsive CSS, HTTP smoke, and the
  production build passed, while screenshot QA is deferred to the already-required Impeccable
  review task rather than being falsely reported.
- Kept the MapLibre map independent of an external basemap: committed Pacoima boundary/tile/site
  geometry is sufficient for the core decision path and remains usable offline. Layers are fetched
  only when selected and cached in client state; budget changes call only the deterministic
  optimizer, never a FortyGuard route.
- Added an allow-listed same-origin Next proxy rather than exposing deployment-specific API routing
  throughout client code. HTTP smoke caught and corrected an initial duplicated `/v1` path before
  acceptance; the final proxy passes all real API shapes and fails visibly when FastAPI is absent.
- Split custom-budget preview from commit after review found that disabling the range input on its
  first change could lock a drag at the first step. The slider now previews continuously and
  optimizes on pointer or keyboard commit, while preset buttons optimize immediately.
- The Impeccable audit found that one shared error state could discard the entire valid workspace
  after a layer, site, or budget failure. Split fatal bootstrap failure from recoverable operation
  errors, kept the last validated state visible, and delayed candidate selection until matching
  site evidence validates so the UI cannot display a mixed evidence record.
- Kept “Why this site?” deterministic: the service first proves the candidate belongs to the
  portfolio at the requested budget, then restates only its typed evidence and limitations. An LLM
  would not add decision evidence for the golden path, so optional LLM mode remains unimplemented
  instead of adding latency and hallucination surface for presentation value alone.
- Proved zero vendor use in the golden browser path with two independent signals: no observed
  request URL names FortyGuard, and the API's committed credit counters are identical before and
  after both budget scenarios. The E2E explicitly forces `FORTYGUARD_LIVE=0`; Vitest excludes the
  Playwright directory so browser and unit runners retain separate discovery contracts.
- Added the architecture-specified demo validator when the proof task found it absent. It exercises
  the deployed HTTP boundary instead of importing service functions, validates responses through
  the production Pydantic models, repeats each golden optimization to detect nondeterminism, and
  compares credit status around the entire path so deployment validation remains fail-closed.
- Rejected Sites deployment for the existing app because its required Vite/Cloudflare Worker shape
  cannot run the Python API without replacing validated architecture. Packaged the unchanged Next
  standalone server and FastAPI process as one Docker Space instead, with only port 7860 exposed,
  same-origin API rewrites, and `FORTYGUARD_LIVE=0`. The exact local production layout passes the
  API validator and hosted-URL Playwright path; remote publication is pending Hugging Face login.
- A user pre-deployment screenshot revealed that the original E2E accepted map controls while all
  GeoJSON remained blank. Runtime inspection isolated the MapLibre/Next worker regression (style
  never loaded and source features stayed at zero). Pinned the documented last-known-good 5.16.0
  release and changed readiness/tests to wait for MapLibre `idle`, preventing the same false pass.
- Reversed the earlier boundary-only map decision after user testing showed that technically valid
  tiles were not geographically interpretable. Added a cached same-origin OpenStreetMap tile proxy,
  visible attribution, exact-value hover, and active-site symbology while keeping the analysis
  independently usable when the basemap is unavailable. Readiness now proves queryable GeoJSON
  rather than waiting on external raster tiles.
- Expanded the CLI-only refresh boundary at the user's explicit request, but kept it administrative:
  the UI requires a server-validated token, `FORTYGUARD_LIVE=1`, canonical idempotency, measured-cost
  preflight, one active job, staged artifact rebuilds, and the 500,000-credit hard reserve. Anonymous
  visitors cannot spend vendor credits, and a failed refresh leaves the last validated cache active.
- Enabled the requested Gemma model through OpenRouter only as a grounded wording layer. The model
  receives one selected site's validated evidence, cannot alter ranking/evidence/limitations, and
  is rejected for prohibited claims or new numbers. File caching and a visible deterministic
  fallback keep the judge path reliable when the free model, key, or network is unavailable.
- A user-triggered refresh exposed an uncaught network exception during the credit preflight. Kept
  the preflight fail-closed and added a specific HTTP 503 path stating that no paid jobs ran and the
  validated cache remains active; restarted the local API with vendor network access rather than
  weakening credit checks or automatically retrying a paid submission.

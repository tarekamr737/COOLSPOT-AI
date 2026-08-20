# AGENTS.md

## Mission
Ship COOLSPOT AI as a working hackathon MVP: turn FortyGuard heat intelligence into a defensible cooling-investment plan for Pacoima, Los Angeles.

## Read order
1. Read this file.
2. Read `PRODUCT.md` for scope and acceptance criteria.
3. Read `ARCHITECTURE.md` for contracts and implementation.
4. Execute only the next unchecked item in `TASKS.md`.
5. Do not invent new scope unless a blocker makes it necessary.

## Operating rules
- Build working software, not a prototype slideshow.
- Prefer the smallest correct implementation.
- Core ranking and optimization must be deterministic; never delegate them to an LLM.
- Never fabricate data, API fields, endpoint access, costs, population, ridership, cooling effects, or precision.
- FortyGuard docs/runtime responses outrank assumptions in these files.
- If docs and runtime disagree, code to runtime behavior and record the difference.
- Keep secrets server-side. Never expose `FORTYGUARD_API_KEY` to the browser.
- Validate all GeoJSON, coordinates, dates, budgets, and numeric ranges at boundaries.
- Use typed schemas at every external/API boundary.
- Cache all external data used in the demo.
- Fail visibly with a useful message; never silently substitute fake live data.

## FortyGuard credit discipline
- Total hackathon allocation: 2,000,000 credits.
- Preserve at least 500,000 credits for final verification/demo.
- No development batch may run if projected remaining credits would fall below that reserve.
- Default to `FORTYGUARD_LIVE=0`; use committed fixtures for normal development/tests.
- Before the first live request, query/record current credit usage.
- For each new endpoint/request shape: make ONE minimal live request, re-check usage, and record the observed delta.
- Estimate batch cost from observed deltas before running it.
- Cache by canonical request hash; identical successful requests must never be repeated.
- Failed tasks are not assumed free unless the API reports failure according to documented behavior.
- Poll existing `activity_id`s; never resubmit merely because processing is slow.
- Start broad analysis at 100 m granularity. Use finer granularity only if it changes the MVP decision.
- Premium-only endpoints are optional until runtime access is confirmed.
- Never infer plan access from the 2M-credit balance alone.

## API usage order
1. Heatmap `tcm`.
2. Heatmap `persistence`.
3. Heatmap `exceedance` only if it adds ranking value.
4. Environmental parameters only for top-ranked sites.
5. Satellite/street-view segmentation only for a small top-site sample and only if access exists.
6. Heat Intelligence reports are optional, not an MVP dependency.

## Data truth
- Use Pacoima as the pilot; target the official/neighborhood boundary and verify final AOI is <10 mi².
- Store the committed boundary in `data/processed/pacoima_aoi.geojson`.
- External public data must include source, retrieval date, and license/usage notes.
- Prefer LA Metro/City/Census authoritative data over scraped summaries.
- Ridership must mean measured/published ridership; GTFS alone is not ridership.
- `people protected`, `lives saved`, and exact future temperature reductions are prohibited claims.
- Call the main output `modeled priority/impact score` and expose uncertainty.

## UI / UX
- Every UI/UX task MUST use the Impeccable skill in the coding-agent environment.
- Discover/read the Impeccable skill instructions before changing visual design, layout, typography, color, interaction, responsiveness, or accessibility.
- If Impeccable is unavailable, stop that UI task and report the missing prerequisite; do not replace it with improvised design.
- Preserve existing functional behavior while applying Impeccable recommendations.
- Desktop-first map experience, but no broken mobile layout.
- Accessibility is required: keyboard navigation, labels, contrast, focus states, reduced-motion support.

## Runtime AI
- AI is explanation-only: summarize structured evidence and optimization results.
- Default to deterministic templates; optional LLM explanations may be enabled and cached.
- The LLM must never invent evidence, costs, effects, or reasons absent from the structured payload.
- Keep prompts short and structured; send only the selected site's data, not the full dataset.

## Engineering
- Python: type hints, Pydantic, Ruff, Pytest.
- TypeScript: strict mode, linting, schema validation for API responses.
- Keep modules small and cohesive; avoid premature abstractions.
- No agent framework unless a concrete requirement appears.
- No database for MVP unless file-backed data becomes a blocker.
- Prefer GeoJSON/GeoParquet fixtures and deterministic preprocessing.
- Optimization uses OR-Tools CP-SAT with integer-scaled coefficients.
- At most one mutually exclusive intervention per candidate site in MVP.
- Keep configurable weights/costs in versioned config, not scattered constants.

## Testing
- Unit-test scoring, normalization, candidate generation, budget constraints, and credit governor.
- Integration-test FortyGuard adapter against fixtures.
- Test optimizer determinism and `total_cost <= budget`.
- E2E-test the golden demo path.
- No live FortyGuard calls in CI.

## Token discipline
- Do not rewrite these docs during implementation.
- Do not produce long planning monologues; act on the next task.
- Inspect only files needed for the current task.
- Reuse existing utilities before creating new ones.
- Prefer targeted search over reading entire generated/vendor directories.
- After each task: run the narrowest relevant tests, then update one checkbox in `TASKS.md`.
- Keep status updates to: changed / tested / blocker.

## Definition of done
The deployed demo can load cached real Pacoima data, show heat/exposure/vulnerability layers, optimize a portfolio under a changed budget without new FortyGuard calls, explain any selected recommendation with evidence, disclose uncertainty, and complete the golden path without errors.

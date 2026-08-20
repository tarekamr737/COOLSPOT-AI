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

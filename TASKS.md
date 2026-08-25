# TASKS.md

> Execute top-to-bottom.
> Mark an item complete only after its acceptance test passes.
> Preserve the existing deterministic architecture, cached judge mode, source provenance, and credit governor.

---

## 1 — Street View evidence extraction

- [x] Add a deterministic Street View feature extractor for cached `/v1/streetview` responses.
- [x] Derive transparent per-view segmentation metrics where available:
  - `tree_pct`
  - `grass_pct`
  - `sky_pct`
  - `road_pct`
  - `sidewalk_pct`
  - `building_pct`
  - `image_date`
- [x] Aggregate front/back views conservatively without calling them direct shade measurements.
- [x] Add a `street_context_confidence` based on:
  - number of usable views,
  - imagery availability,
  - imagery age,
  - segmentation completeness.
- [x] Add a derived `shade_intervention_evidence_score`.
- [x] Clearly document that this is **intervention-screening evidence**, not proof that a stop is unshaded.
- [x] Parse all currently cached Street View results for the `$1M` portfolio.
- [x] Persist normalized site evidence to a small versioned processed artifact.
- [x] Add unit tests for:
  - missing views,
  - malformed segmentation,
  - stale imagery,
  - deterministic aggregation,
  - score bounds.

**Acceptance:** cached Street View evidence changes site confidence/opportunity deterministically while preserving all limitations.

---

## 2 — Upgrade candidate confidence + feasibility

- [x] Remove the universal `0.5 / 0.5` candidate treatment where richer evidence exists.
- [x] Keep neutral fallback values only for genuinely unverified candidates.
- [x] Define evidence-based confidence rules in versioned config.
- [x] Define intervention-specific feasibility/suitability inputs.

### Shade structures

Use only defensible signals such as:

- heat severity,
- persistence/exceedance,
- published transit exposure,
- Street View vegetation context,
- Street View sky/open-street context,
- evidence confidence.

Do **not** claim Street View proves useful shade coverage throughout the day.

### Tree canopy

Use:

- heat severity,
- public-site compatibility,
- vegetation/canopy opportunity where evidenced,
- environmental context,
- evidence confidence.

### Cool pavement

Use only after verified paved/public surface geometry exists.

- [x] Add evidence records explaining every non-neutral feasibility/confidence adjustment.
- [x] Surface raw inputs and derived values through the API/site drawer.

**Acceptance:** two sites with different verified evidence can receive different feasibility/confidence scores for explainable reasons.

---

## 3 — Add FortyGuard `exceedance`

- [x] Confirm current documented request schema against the existing FortyGuard adapter/models.
- [x] Add/validate `analytic_type=exceedance` support.
- [x] Measure one real request's credit delta using the existing governor workflow.
- [x] Abort further work if projected reserve would fall below `500,000`.
- [x] Cache one real Pacoima exceedance dataset for the frozen analysis period.
- [x] Normalize exceedance into the heat feature model.
- [x] Update default heat severity:

```text
heat_score =
0.40 × temperature
+ 0.35 × persistence
+ 0.25 × exceedance
```

- [x] Keep weights versioned/configurable.
- [x] Add comparison test showing whether exceedance materially changes rankings.
- [x] Update methodology and provenance.

**Acceptance:** exceedance is real, cached, source-attributed, deterministic, and visible in site evidence.

---

## 4 — Add FortyGuard `time_of_measure`

- [x] Add/validate `analytic_type=time_of_measure`.
- [x] Measure request credit cost before any repeated request.
- [x] Cache one real Pacoima result if supported by the hackathon key.
- [x] Store peak-hour context per tile/site.
- [x] Use it for explanation/context only unless strong evidence justifies scoring.
- [x] Never imply that peak temperature time equals peak pedestrian volume.
- [x] Surface a concise label such as:

```text
Peak heat observed around: 15:00
```

**Acceptance:** peak timing improves explanation without introducing unsupported exposure claims.

---

## 5 — Add Environmental Parameters for finalists

- [x] Probe `/v1/env_params` with one minimal valid request.
- [x] Measure observed credit cost.
- [x] Continue only if supported and credit-safe.
- [x] Prefer no more than three useful parameters:
  - apparent temperature or heat index,
  - relative humidity,
  - solar irradiance.
- [x] Run only for a small deterministic top-N finalist set, initially `N <= 10`.
- [x] Cache every completed response.
- [x] Persist normalized environmental evidence.
- [x] Add `thermal_stress_context` to candidate/site evidence.
- [x] Do not fabricate a medical-risk score.
- [x] Recompute evidence confidence where appropriate.

**Acceptance:** selected finalists show point-level FortyGuard environmental context with source/date/limitations.

---

## 6 — Make optimization intervention-aware

Replace the current generic value calculation with intervention-specific modeled benefit.

### Shade

```text
shade_value =
priority_score
× shade_suitability
× feasibility
× confidence
```

### Tree canopy

```text
tree_value =
priority_score
× tree_suitability
× feasibility
× confidence
```

### Cool pavement

```text
pavement_value =
priority_score
× pavement_suitability
× feasibility
× confidence
```

- [x] Keep all derived factors in `[0,1]`.
- [x] Keep CP-SAT deterministic.
- [x] Do not use an LLM in ranking or optimization.
- [x] Preserve:
  - budget constraint,
  - one intervention per site,
  - compatibility rules.
- [x] Add explanation fields showing why each intervention received its value.
- [x] Add regression tests proving deterministic portfolios.
- [x] Add tests showing intervention evidence can alter portfolio selection.

**Acceptance:** COOLSPOT optimizes **intervention fit + priority**, not merely hotspot priority.

---

## 7 — Activate cool-pavement candidates

- [x] Acquire authoritative public roadway/corridor/paved-surface geometry for Pacoima.
- [x] Record source, retrieval date, license notes, and geometry provenance.
- [x] Generate only candidates on verified public paved geometry.
- [x] Keep existing safety requirements for:
  - surface condition,
  - traction,
  - glare,
  - drainage,
  - pedestrian radiant exposure,
  - product compatibility.
- [x] Attempt at most one small `/v1/satellite` capability probe if it materially improves surface evidence.
- [x] Measure the real credit delta.
- [x] If supported and cost-safe, enrich only top pavement finalists.
- [x] If unsupported, continue with authoritative public geometry instead of blocking the feature.
- [x] Add at least one valid cool-pavement candidate if evidence permits.
- [x] Otherwise remove cool pavement from the golden demo and clearly explain why. *(Not applicable: verified candidates are selectable.)*

**Acceptance:** no UI claims three operational intervention families while the third is impossible to select.

---

## 8 — Scenario presets + robustness analysis

Add four versioned scoring presets.

### Balanced

```text
Heat          0.40
Exposure      0.30
Vulnerability 0.20
Opportunity   0.10
```

### Heat-first

```text
Heat          0.50
Exposure      0.25
Vulnerability 0.15
Opportunity   0.10
```

### Equity-first

```text
Heat          0.30
Exposure      0.25
Vulnerability 0.35
Opportunity   0.10
```

### Exposure-first

```text
Heat          0.30
Exposure      0.40
Vulnerability 0.20
Opportunity   0.10
```

- [x] Add preset selector to API contracts.
- [x] Re-score/re-optimize without FortyGuard calls.
- [x] Compute:

```text
robustness_score =
number_of_presets_selecting_site
/
number_of_presets_tested
```

- [x] Surface labels such as:

```text
Selected in 4/4 planning scenarios
```

- [x] Do not present robustness as statistical confidence.
- [x] Add tests for all four presets.

**Acceptance:** judges can change planning priorities and see which recommendations remain stable at zero vendor cost.

---

## 9 — UI/UX upgrade with Impeccable

> All UI/UX changes must use the **Impeccable skill**.

- [x] Re-run Impeccable against the new golden path before coding UI changes.
- [x] Add scenario preset control without cluttering the main workspace.
- [x] Upgrade recommendation/site drawer with:
  - FortyGuard heat,
  - persistence,
  - exceedance,
  - peak timing,
  - environmental context,
  - Street View original/segmented context,
  - intervention evidence score,
  - feasibility,
  - confidence,
  - robustness,
  - cost,
  - sources,
  - limitations.
- [x] Clearly separate:
  - observed evidence,
  - derived screening scores,
  - planning assumptions.
- [x] Add concise visual indicators for:
  - `Verified evidence`
  - `Modeled`
  - `Planning assumption`
  - `Field verification required`
- [x] Keep map-first hierarchy.
- [x] Keep budget recalculation visibly at `0 FortyGuard credits`.
- [x] Re-run Impeccable after implementation.
- [x] Fix accessibility, responsiveness, hierarchy, empty/error states, and keyboard navigation.

**Acceptance:** a judge can understand why a site and intervention were selected in under 15 seconds.

---

## 10 — Evidence + methodology audit

- [x] Update `PRODUCT.md`.
- [x] Update `ARCHITECTURE.md`.
- [x] Update `README.md`.
- [x] Update `EVIDENCE.md`.
- [x] Update `BUILDLOG.md`.
- [x] Update `data/sources.json`.
- [x] Update capability snapshot.
- [x] Update all scoring/config documentation.
- [x] Remove outdated claims about universal `0.5` confidence/feasibility.
- [x] Remove any claim that cool pavement is supported if still unavailable. *(Not applicable: exact StreetsLA geometry now supports 20 tested candidates.)*
- [x] Verify every numeric claim is traceable to:
  - FortyGuard,
  - authoritative public data,
  - cited research,
  - or an explicitly labeled model/config assumption.

**Acceptance:** README, application, API, processed data, and methodology tell the same story.

---

## 11 — Optional Heat Intelligence bonus

Do only after all previous tasks pass.

- [x] Verify current `/v1/heat_intelligence` documentation.
- [x] Probe once only if hackathon-key access and credits permit.
- [x] Never use the report to rank or optimize sites.
- [x] Use only as supporting evidence/reporting for a top recommendation.
- [x] Cache the result and record cost/provenance.
- [x] Gracefully omit the feature if unavailable.

**Acceptance:** optional report strengthens explanation but is never a core dependency.

---

## 12 — Full regression + adversarial audit

### Backend

- [x] `ruff`
- [x] `mypy`
- [x] full `pytest`
- [x] fixture parsing
- [x] scoring
- [x] candidate generation
- [x] scenario presets
- [x] robustness
- [x] optimizer
- [x] credit governor
- [x] optional-endpoint failure paths

### Frontend

- [x] lint/type checks
- [x] production build
- [ ] component/unit tests
- [ ] Playwright golden path
- [ ] responsive test
- [ ] accessibility check

### Claim audit

Try to disprove:

- [ ] “This stop is unshaded.”
- [ ] “This intervention will lower temperature by exactly X°C.”
- [ ] “X people will be saved.”
- [ ] “Vulnerability score equals people affected.”
- [ ] “Street View proves all-day shade.”
- [ ] “Environmental parameters predict medical outcomes.”
- [ ] “Robustness score is statistical confidence.”

Fix any UI/API wording that implies those claims.

**Acceptance:** no unsupported claim remains.

---

## 13 — Deploy the judge build

- [ ] Deploy production web/API in frozen demo mode.
- [ ] Run `scripts/validate_demo.py` against production.
- [ ] Run full Playwright golden path against production URLs.
- [ ] Confirm application works when FortyGuard is unavailable.
- [ ] Confirm budget and scenario changes make zero FortyGuard calls.
- [ ] Confirm cached Street View and environmental evidence load correctly.
- [ ] Verify server-only secrets.
- [ ] Verify CORS/security configuration.
- [ ] Test Chrome desktop + mobile viewport.
- [ ] Test one clean incognito session.

**Acceptance:** deployed golden path completes without errors.

---

## 14 — Freeze final hackathon evidence

- [ ] Record exact data dates.
- [ ] Record final FortyGuard credit usage.
- [ ] Preserve at least `500,000` credits unless explicitly justified otherwise.
- [ ] Freeze processed artifacts used for judging.
- [ ] Generate hashes/manifests for frozen evidence.
- [ ] Disable unnecessary live experimentation.
- [ ] Tag final judge-ready commit.

**Acceptance:** final submission is reproducible from committed evidence.

---

## 15 — Final 2–3 minute judge path

Prepare this exact flow:

1. Open Pacoima.
2. State:
   **“Cities already know where it is hot. The problem is deciding what to fund.”**
3. Show Heat.
4. Show Persistence.
5. Show Exceedance.
6. Set `$500k`.
7. Open the #1 recommendation.
8. Show:
   - heat evidence,
   - transit/public exposure,
   - vulnerability,
   - Street View evidence,
   - environmental parameters,
   - intervention suitability,
   - confidence,
   - cost,
   - sources.
9. Switch to `$1M`.
10. Show portfolio changes with:
    **`0 additional FortyGuard credits`**
11. Change `Balanced` → `Equity-first`.
12. Highlight recommendations that remain selected.
13. Show:
    **`Robust across 4/4 scenarios`**
14. Open methodology/limitations.
15. Finish:
    **“FortyGuard tells us where heat is. COOLSPOT tells a city what to fund next.”**

**Acceptance:** complete demo comfortably within 3 minutes without relying on live external APIs.

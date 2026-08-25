# Decision configuration

These versioned files are the authoritative assumptions for COOLSPOT's deterministic screening
and optimization. They contain planning rules, not measured intervention effects. Changing a
hashed config requires rebuilding its dependent processed artifact and rerunning the focused tests.

## Calculation order

1. `scoring.json` normalizes raw evidence within the frozen Pacoima tile set and builds the four
   component scores: heat, exposure, vulnerability, and cooling opportunity.
2. `scoring.json` also stores the canonical Balanced priority used in the committed candidate
   artifact. `scenarios.json` reweights those same four committed components at request time; it
   never reacquires or renormalizes vendor data.
3. `candidates.json` applies intervention suitability, feasibility, and evidence confidence:

   `modeled impact = scenario priority × suitability × feasibility × confidence`

4. `optimizer.json` converts that value to an integer coefficient and uses CP-SAT to maximize total
   modeled impact under the budget and one-intervention-per-site constraints.

No LLM participates in these calculations.

## Tile components

`scoring.json` uses 2nd/98th percentile winsorized min-max normalization. Missing composite inputs
are preserved and the remaining weights are renormalized; a constant feature receives `0.0`.

| Component | Configured composition |
| --- | --- |
| Heat | temperature `0.40`, persistence `0.35`, historical exceedance `0.25` |
| Exposure | ACS population context `0.40`, published patronage `0.40`, POI count `0.10`, transit-stop count `0.10` |
| Vulnerability | children, older adults, poverty, and no-vehicle rates at `0.25` each |
| Cooling opportunity | mapped public-site compatibility `0.60`, mapped transit waiting location `0.40` |

Cooling opportunity does not claim observed canopy, shade, or surface condition. Population is
intersecting-tract context, not a tile population or people-served count. GTFS is not ridership;
only the separately published Metro patronage fields supply activity evidence.

## Planning scenarios

The weight order below is heat / exposure / vulnerability / cooling opportunity.

| Preset | Weights |
| --- | --- |
| Balanced | `0.40 / 0.30 / 0.20 / 0.10` |
| Heat-first | `0.50 / 0.25 / 0.15 / 0.10` |
| Equity-first | `0.30 / 0.25 / 0.35 / 0.10` |
| Exposure-first | `0.30 / 0.40 / 0.20 / 0.10` |

Scenario robustness is the number of these four presets that select a site. It is not statistical
confidence, probability, a guarantee, or sensitivity across every plausible assumption.

## Candidate factors and fallbacks

`0.5` is a neutral deterministic fallback only for an evidence dimension that remains unverified:

- feasibility is currently `0.5` for every candidate because field/engineering checks are absent;
- confidence is replaced by exact-site Street View confidence where that cached evidence exists;
- shade suitability is the mean of available exact-site open-sky and low-tree context;
- tree suitability uses exact-site low-tree context;
- unmatched shade/tree suitability remains `0.5`;
- an eligible exact StreetsLA pavement segment receives `1.0` data-level suitability, while its
  feasibility and confidence remain `0.5` pending field review.

These scalars are not probabilities, observed effects, or construction findings. Satellite surface
context and environmental finalist values are displayed evidence only: neither changes candidate
priority, suitability, feasibility, confidence, rank, or optimization. `intervention_evidence.json`
lists permitted evidence and mandatory safety gates; the active numeric rules are in
`candidates.json`.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `scoring.json` | Normalization, within-component weights, canonical Balanced tile priority, join limits, and missing-data rules |
| `scenarios.json` | Complete four-preset runtime priority catalog |
| `candidates.json` | Candidate selection, exact-site confidence/suitability rules, pavement geometry rule, and neutral fallbacks |
| `intervention_evidence.json` | Allowed evidence and unresolved feasibility/safety gates by intervention family |
| `streetview_evidence.json` | Exact-frame aggregation and normalized street-context evidence weights |
| `environmental_parameters.json` | Three displayed finalist context fields and their claim limitations; no scoring |
| `fortyguard_heatmaps.json` | Historical acquisition parameters and the disclosed 30 °C planning threshold |
| `optimizer.json` | Budget bounds/presets, deterministic CP-SAT settings, objective meaning, equity context, and robustness limitation |

Planning costs and price evidence live in `data/processed/interventions.json`; they are allowances,
not quotes. Source dates, licenses, and usage notes live in `data/sources.json`.

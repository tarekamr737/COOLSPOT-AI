const geometry = { type: "Point" as const, coordinates: [-118.42, 34.27] as [number, number] };
const polygon = {
  type: "Polygon" as const,
  coordinates: [[[-118.43, 34.26], [-118.41, 34.26], [-118.41, 34.28], [-118.43, 34.26]]],
};

export const candidates = Array.from({ length: 20 }, (_, index) => ({
  id: `shade_structure:site-${index}`,
  site_id: `site-${index}`,
  site_name: index === 0 ? "Van Nuys / Herrick" : `Pacoima site ${index + 1}`,
  site_type: "transit_stop",
  site_source_ids: ["la_metro_gtfs_bus"],
  tile_id: String(index + 1),
  intersecting_tile_count: 1,
  tile_selection: "containing_tile",
  intervention_type: "shade_structure",
  planning_cost_usd: 50_000,
  benefit_score: 0.84 - index * 0.01,
  suitability_score: index === 0 ? 0.7 : 0.5,
  equity_score: 0.62,
  feasibility_score: 0.5,
  confidence: index === 0 ? 0.791667 : 0.5,
  value_explanation: {
    formula: "priority_score × suitability_score × feasibility_score × confidence_score",
    factors: {
      priority_score: 0.84 - index * 0.01,
      suitability_score: index === 0 ? 0.7 : 0.5,
      feasibility_score: 0.5,
      confidence_score: index === 0 ? 0.791667 : 0.5,
    },
    modeled_benefit_score:
      (0.84 - index * 0.01) * (index === 0 ? 0.7 : 0.5) * 0.5 *
      (index === 0 ? 0.791667 : 0.5),
    suitability_basis: ["Exact-site screening evidence."],
    limitation: "This is a relative screening product, not a measured cooling effect or guaranteed outcome.",
  },
  thermal_stress_context: index === 0 ? {
    finalist_rank: 1,
    candidate_id: "shade_structure:site-0",
    site_id: "site-0",
    site_name: "Van Nuys / Herrick",
    tile_id: "1",
    latitude: 34.271105,
    longitude: -118.414991,
    observed_temperature_c: 35.9398,
    apparent_temperature_c: 35.3,
    relative_humidity_percent: 24.3,
    clear_sky_ghi_vendor_value: 779.49,
    observed_at: "2026-08-20T14:00:00-08:00",
    vendor_timezone: "GMT-8",
    vendor_timezone_offset_hours: -8,
    request_hash: "9".repeat(64),
    activity_id: "0bd748b2-88dd-498c-ae5d-7aac35f07f92",
    source_artifact: { path: "data/processed/pacoima_environmental_sites/site-0.json", sha256: "8".repeat(64) },
    evidence_confidence: {
      assessment: "source_complete",
      configured_fields_present: "3 of 3",
      basis: "All three configured fields are present in the exact completed response.",
      limitation: "Source completeness does not establish medical risk, individual exposure, intervention feasibility, or a guaranteed cooling outcome.",
    },
  } : null,
  satellite_surface_context: null,
  evidence: ["observed_heat", "exposure", "vulnerability", "applicability", "planning_assumption"].map((kind) => ({
    kind,
    statement: `${kind.replaceAll("_", " ")} evidence for this screened Pacoima candidate.`,
    source_artifact_ids: ["pacoima_tile_feature_table"],
  })),
  geometry,
}));

export const intervention = {
  id: "shade_structure",
  label: "Shade structure",
  description: "A fixed shelter sized for a transit waiting area.",
  applicability: {
    eligible_site_types: ["transit_stop"],
    screening_rule: "Screen published transit stop locations only.",
    preconstruction_checks: ["Verify shade", "Confirm clearances"],
    exclusion_rule: "Exclude sites that fail field review.",
  },
  planning_cost: {
    estimate_usd: 50_000,
    low_usd: 35_000,
    high_usd: 75_000,
    unit: "one transit-stop shelter site",
    basis: "A documented planning assumption, not a contractor quote.",
    source_ids: ["ladot"],
  },
  benefit_evidence: {
    kind: "qualitative",
    qualitative_benefit: "Shade can reduce direct solar exposure.",
    transfer_limit: "Actual performance depends on site conditions.",
    source_ids: ["ladot"],
  },
  uncertainty: {
    level: "medium",
    summary: "Mapped locations do not establish existing shade or constructability.",
    factors: ["Existing shade unknown", "Utilities unknown"],
  },
  lifespan_maintenance: {
    expected_lifespan: "Determine during design.",
    maintenance_note: "Budget for inspection and repair.",
    source_ids: ["ladot"],
  },
};

export const pilot = {
  name: "Pacoima, Los Angeles",
  boundary: { type: "FeatureCollection", features: [{ type: "Feature", geometry: polygon, properties: { area_sq_mi: 7.763 } }] },
  area_sq_mi: 7.763,
  crs: "EPSG:4326",
  granularity_m: 100,
  analysis_date: "2024-07-15",
  budget_presets_usd: [250_000, 500_000, 1_000_000],
  default_budget_usd: 500_000,
  scoring_presets: ["balanced", "heat_first", "equity_first", "exposure_first"],
  default_scoring_preset: "balanced",
  candidate_count: 20,
  available_layers: ["heat", "persistence", "exposure", "vulnerability"],
};

export function layer(name = "heat") {
  const properties = name === "persistence"
    ? { layer: "persistence", tile_id: "1", persistence_hours: 7.04, threshold_c: 30, direction: "above", persistence_score: 0.8, combined_heat_score: 0.75 }
    : { layer: "heat", tile_id: "1", average_temperature_c: 35.45, temperature_score: 0.8, combined_heat_score: 0.75 };
  return { type: "FeatureCollection", layer: name, source_date: "2024-07-15", generated_at: "2026-08-21T00:00:00Z", cached: true, features: [{ type: "Feature", geometry: polygon, properties }], limitations: ["Screening data only."] };
}

export function portfolio(budget = 500_000) {
  const count = budget === 1_000_000 ? 20 : budget === 250_000 ? 5 : 10;
  return {
    solver_status: "optimal",
    scoring_preset: "balanced",
    scoring_weights: { heat: 0.4, exposure: 0.3, vulnerability: 0.2, cooling_opportunity: 0.1 },
    budget_usd: budget,
    total_cost_usd: count * 50_000,
    unused_budget_usd: budget - count * 50_000,
    selected_count: count,
    selected_candidate_ids: candidates.slice(0, count).map((candidate) => candidate.id),
    total_modeled_impact_score: count * 0.2,
    integer_objective_value: count * 200_000,
    objective_scale: 1_000_000,
    category_counts: { shade_structure: count, tree_canopy: 0, cool_pavement: 0 },
    equity_summary: { mean_selected_vulnerability_score: 0.62, score_sum: count * 0.62, note: "Equity context is not a population count." },
    site_robustness: Array.from({ length: count }, (_, index) => ({
      site_id: `site-${index}`,
      selected_in_presets: ["balanced", "heat_first", "equity_first", "exposure_first"],
      presets_selected: 4,
      presets_tested: 4,
      robustness_score: 1,
    })),
  };
}

export const methodology = {
  version: "1.0",
  scoring: { version: "1.0", priority_weights: { heat: 0.4, exposure: 0.3, vulnerability: 0.2, cooling_opportunity: 0.1 }, heat_weights: { temperature: 0.4, persistence: 0.35, exceedance: 0.25 }, missing_strategy: "Neutral score", point_join_note: "Nearest sites are joined within the configured distance." },
  heat_provenance: { source: "FortyGuard Heatmap API", source_url: "https://docs-api.fortyguard.com/docs/create-heatmap", active_analysis_date: "2026-08-20", exceedance_analysis_date: "2024-07-15", exceedance_threshold_c: 30, exceedance_direction: "above", exceedance_request_hash: "01b10110a2455dd1c8a33769eca3b1d9eb2ee1949d4e626cb4236a28907d7a58", exceedance_activity_id: "e754402c-a9c8-4816-a981-786aa3e45f77", exceedance_artifact_sha256: "a".repeat(64), observed_credit_delta: 4220, limitation: "Exceedance is historical context and is not contemporaneous with active heat evidence." },
  peak_hour_provenance: { source: "FortyGuard Heatmap API", source_url: "https://docs-api.fortyguard.com/docs/create-heatmap", analysis_date: "2024-07-15", timezone: "UTC", request_hash: "393a609d34ae19d5124b911b0e2d94d6c59409976357519b301b88bc5da56991", activity_id: "eaa617ad-07b3-47db-9094-faa26c8eeb79", artifact_sha256: "b".repeat(64), observed_credit_delta: 4220, limitation: "Peak temperature hour is historical context, not evidence of peak pedestrian volume." },
  candidate_generation: { screening_score_note: "Scores are for screening only.", representative_tile_rule: "Choose the highest-priority intersecting tile." },
  optimization: { budget_presets_usd: [250_000, 500_000, 1_000_000], custom_budget_min_usd: 50_000, custom_budget_max_usd: 2_000_000, determinism_note: "Fixed integer coefficients and deterministic tie breaking.", objective_note: "Maximizes modeled impact under the selected budget.", equity_note: "Reports equity context without claiming population outcomes." },
  interventions: {
    cost_basis: { disclaimer: "Planning assumptions are not contractor quotes." },
    sources: [{ id: "ladot", title: "Shade pilot", publisher: "LADOT", url: "https://ladot.lacity.gov/", published_at: "2023-05-25", retrieved_at: "2026-08-21", supports: ["Planning cost context"] }],
    interventions: [intervention],
  },
  limitations: ["Field review is required."],
};

export const status = {
  mode: "cached_demo",
  external_calls_on_read: false,
  refresh_available: false,
  explanation_mode: "template",
  heat_data_date: "2024-07-15",
  heat_data_generated_at: "2026-08-21T00:00:00Z",
  public_data_retrieved_at: "2026-08-21",
  capabilities_evaluated_at: "2026-08-21",
  credits: { total: 2_000_000, used: 8_440, remaining: 1_991_560, hard_reserve: 500_000 },
  capabilities: [],
  layers: ["heat", "persistence", "exposure", "vulnerability"],
  candidate_count: 20,
  candidate_source_artifacts: [],
};

export function site(index = 0) {
  return {
    site_id: candidates[index].site_id,
    site_name: candidates[index].site_name,
    geometry,
    street_view_evidence: index === 0 ? {
      site_id: candidates[index].site_id,
      coordinates: { latitude: 34.273715, longitude: -118.411903 },
      frames: [{
        direction: "front",
        image_date: "2024-10-01",
        original_image_available: true,
        segmented_image_available: true,
        segments: [
          { label: "building", percentage: 6.53 },
          { label: "road", percentage: 40.33 },
          { label: "sky", percentage: 43.47 },
          { label: "tree", percentage: 0.65 },
        ],
        metrics: { tree_pct: 0.65, grass_pct: null, sky_pct: 43.47, road_pct: 40.33, sidewalk_pct: null, building_pct: 6.53 },
      }],
      aggregate: {
        view_count: 1,
        metrics: { tree_pct: 0.65, grass_pct: null, sky_pct: 43.47, road_pct: 40.33, sidewalk_pct: null, building_pct: 6.53 },
        contributing_views: { tree_pct: 1, grass_pct: 0, sky_pct: 1, road_pct: 1, sidewalk_pct: 0, building_pct: 1 },
      },
      street_context_confidence: {
        score: 0.791667,
        usable_view_count: 1,
        oldest_image_age_days: 690,
        components: { usable_views: 0.5, imagery_availability: 1, imagery_age: 1, segmentation_completeness: 0.666667 },
      },
      shade_intervention_evidence: {
        score: 0.565329,
        open_sky_context: 0.4347,
        low_tree_context: 0.9935,
        street_context_confidence: 0.791667,
        limitation: "Street View segmentation is screening evidence. It does not prove all-day shade, right-of-way, or construction feasibility.",
      },
    } : null,
    options: [{
      candidate: candidates[index],
      tile: {
        tile_id: String(index + 1), geometry: polygon,
        heat: { average_temperature_c: 35.45, persistence_hours: 7.04, exceedance_hours: 6.89, peak_heat_hour_utc: 15, temperature_score: 0.8, persistence_score: 0.78, exceedance_score: 0.74 },
        exposure: { transit_stop_count: 1, published_patronage_activity: 79.79, poi_count: 0 },
        vulnerability: { children_rate: 0.2, older_adult_rate: 0.1, poverty_rate: 0.18, no_vehicle_rate: 0.06 },
        scores: { heat: 0.75, exposure: 0.8, vulnerability: 0.622, cooling_opportunity: 0.4, priority: 0.84 },
        missing_fields: [],
      },
      intervention,
    }],
  };
}

export function explanation(index = 0, budget = 500_000) {
  const candidate = candidates[index];
  return {
    mode: "template",
    model: null,
    fallback_reason: null,
    site_id: candidate.site_id,
    candidate_id: candidate.id,
    budget_usd: budget,
    summary: `At the ${compactBudget(budget)} screening budget, ${candidate.site_name} is selected from structured evidence and contributes ${(
      candidate.value_explanation.modeled_benefit_score
    ).toFixed(3)} modeled impact score to the deterministic portfolio.`,
    why_selected: candidate.evidence.map((item) => item.statement),
    limitations: [
      "This explanation does not predict a site temperature reduction.",
      "Mapped data does not establish constructability.",
      "Planning costs are assumptions, not contractor quotes.",
    ],
    evidence: candidate.evidence,
  };
}

export function streetView(siteId: string) {
  return {
    site_id: siteId,
    available: false,
    image_date: null,
    original_image_url: null,
    segmented_image_url: null,
    segments: {},
    source_label: "FortyGuard Street View Segmentation",
    source_url: "https://docs-api.fortyguard.com/docs/street-view-segmentation",
    limitation: "No verified street segmentation is cached for this site.",
  };
}

function compactBudget(value: number) {
  return `$${Math.round(value / 1_000).toLocaleString()}k`;
}

export const candidateList = {
  version: "1.0", generated_at: "2026-08-21T00:00:00Z",
  counts: { total: 20, unique_sites: 20, shade_structure: 20, tree_canopy: 0, cool_pavement: 0 },
  source_artifacts: [{ id: "pacoima_tile_feature_table", path: "data/processed/pacoima_tile_features.json", sha256: "a".repeat(64) }],
  limitations: ["Screening only."], candidates,
};

export function responseFor(url: string, init?: RequestInit) {
  if (url.endsWith("/pilot")) return pilot;
  if (url.endsWith("/candidates")) return candidateList;
  if (url.endsWith("/data-status")) return status;
  if (url.endsWith("/methodology")) return methodology;
  if (url.includes("/layers/")) return layer(url.split("/").at(-1));
  if (url.endsWith("/optimize")) return portfolio(JSON.parse(String(init?.body)).budget_usd);
  if (url.endsWith("/explanation")) {
    const body = JSON.parse(String(init?.body));
    const index = Math.max(0, candidates.findIndex((candidate) => candidate.id === body.candidate_id));
    return explanation(index, body.budget_usd);
  }
  if (url.endsWith("/street-view")) {
    const id = decodeURIComponent(url.split("/").at(-2) ?? "site-0");
    return streetView(id);
  }
  if (url.includes("/sites/")) {
    const id = decodeURIComponent(url.split("/").at(-1) ?? "site-0");
    const index = Math.max(0, candidates.findIndex((candidate) => candidate.site_id === id));
    return site(index);
  }
  throw new Error(`Unexpected test request: ${url}`);
}

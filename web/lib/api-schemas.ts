import { z } from "zod";

export const layerNames = ["heat", "persistence", "exposure", "vulnerability"] as const;
export const layerNameSchema = z.enum(layerNames);
export type LayerName = z.infer<typeof layerNameSchema>;

const positionSchema = z.tuple([z.number(), z.number()]);
const pointGeometrySchema = z.object({
  type: z.literal("Point"),
  coordinates: positionSchema,
});
const polygonGeometrySchema = z.object({
  type: z.literal("Polygon"),
  coordinates: z.array(z.array(positionSchema)),
});
const multiPolygonGeometrySchema = z.object({
  type: z.literal("MultiPolygon"),
  coordinates: z.array(z.array(z.array(positionSchema))),
});
export const geometrySchema = z.discriminatedUnion("type", [
  pointGeometrySchema,
  polygonGeometrySchema,
  multiPolygonGeometrySchema,
]);
export type Geometry = z.infer<typeof geometrySchema>;

const boundarySchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: polygonGeometrySchema,
      properties: z.record(z.string(), z.unknown()),
    }),
  ),
});

export const pilotSchema = z.object({
  name: z.literal("Pacoima, Los Angeles"),
  boundary: boundarySchema,
  area_sq_mi: z.number().positive().lt(10),
  crs: z.literal("EPSG:4326"),
  granularity_m: z.literal(100),
  analysis_date: z.string(),
  budget_presets_usd: z.array(z.number().int().positive()).min(1),
  default_budget_usd: z.number().int().positive(),
  candidate_count: z.number().int().min(20),
  available_layers: z.array(layerNameSchema),
});
export type Pilot = z.infer<typeof pilotSchema>;

const evidenceSchema = z.object({
  kind: z.enum([
    "observed_heat",
    "exposure",
    "vulnerability",
    "applicability",
    "planning_assumption",
    "street_context",
  ]),
  statement: z.string().min(1),
  source_artifact_ids: z.array(z.string()).min(1),
});

export const candidateSchema = z.object({
  id: z.string().min(1),
  site_id: z.string().min(1),
  site_name: z.string().min(1),
  site_type: z.enum(["transit_stop", "school", "park", "civic", "paved_surface"]),
  site_source_ids: z.array(z.string()).min(1),
  tile_id: z.string().min(1),
  intersecting_tile_count: z.number().int().positive(),
  tile_selection: z.enum(["containing_tile", "highest_priority_intersecting_tile"]),
  intervention_type: z.enum(["shade_structure", "tree_canopy", "cool_pavement"]),
  planning_cost_usd: z.number().int().positive(),
  benefit_score: z.number().min(0).max(1),
  equity_score: z.number().min(0).max(1),
  feasibility_score: z.number().min(0).max(1),
  confidence: z.number().min(0).max(1),
  evidence: z.array(evidenceSchema).min(5),
  geometry: geometrySchema,
});
export type Candidate = z.infer<typeof candidateSchema>;

export const candidateListSchema = z.object({
  version: z.string(),
  generated_at: z.string(),
  counts: z.object({
    total: z.number().int().min(20),
    unique_sites: z.number().int().min(20),
    shade_structure: z.number().int().nonnegative(),
    tree_canopy: z.number().int().nonnegative(),
    cool_pavement: z.number().int().nonnegative(),
  }),
  source_artifacts: z.array(z.object({ id: z.string(), path: z.string(), sha256: z.string() })),
  limitations: z.array(z.string()),
  candidates: z.array(candidateSchema).min(20),
});
export type CandidateList = z.infer<typeof candidateListSchema>;

const heatPropertiesSchema = z.object({
  layer: z.literal("heat"),
  tile_id: z.string(),
  average_temperature_c: z.number(),
  temperature_score: z.number().min(0).max(1),
  combined_heat_score: z.number().min(0).max(1),
});
const persistencePropertiesSchema = z.object({
  layer: z.literal("persistence"),
  tile_id: z.string(),
  persistence_hours: z.number().nonnegative(),
  threshold_c: z.number(),
  direction: z.enum(["above", "below"]),
  persistence_score: z.number().min(0).max(1),
  combined_heat_score: z.number().min(0).max(1),
});
const exposurePropertiesSchema = z.object({
  layer: z.literal("exposure"),
  tile_id: z.string(),
  exposure_score: z.number().min(0).max(1),
  transit_stop_count: z.number().int().nonnegative(),
  published_patronage_activity: z.number().nonnegative().nullable(),
  poi_count: z.number().int().nonnegative(),
  school_count: z.number().int().nonnegative(),
  park_count: z.number().int().nonnegative(),
  library_count: z.number().int().nonnegative(),
  acs_total_population_context: z.number().nonnegative().nullable(),
  missing_fields: z.array(z.string()),
});
const vulnerabilityPropertiesSchema = z.object({
  layer: z.literal("vulnerability"),
  tile_id: z.string(),
  vulnerability_score: z.number().min(0).max(1),
  children_rate: z.number().min(0).max(1).nullable(),
  older_adult_rate: z.number().min(0).max(1).nullable(),
  poverty_rate: z.number().min(0).max(1).nullable(),
  no_vehicle_rate: z.number().min(0).max(1).nullable(),
  acs_tract_geoids: z.array(z.string()),
  missing_fields: z.array(z.string()),
});
const layerPropertiesSchema = z.discriminatedUnion("layer", [
  heatPropertiesSchema,
  persistencePropertiesSchema,
  exposurePropertiesSchema,
  vulnerabilityPropertiesSchema,
]);
export type LayerProperties = z.infer<typeof layerPropertiesSchema>;

export const layerResponseSchema = z.object({
  type: z.literal("FeatureCollection"),
  layer: layerNameSchema,
  source_date: z.string(),
  generated_at: z.string(),
  cached: z.literal(true),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: polygonGeometrySchema,
      properties: layerPropertiesSchema,
    }),
  ),
  limitations: z.array(z.string()),
});
export type LayerResponse = z.infer<typeof layerResponseSchema>;

export const portfolioSchema = z.object({
  solver_status: z.literal("optimal"),
  budget_usd: z.number().int().positive(),
  total_cost_usd: z.number().int().nonnegative(),
  unused_budget_usd: z.number().int().nonnegative(),
  selected_count: z.number().int().nonnegative(),
  selected_candidate_ids: z.array(z.string()),
  total_modeled_impact_score: z.number().nonnegative(),
  integer_objective_value: z.number().int().nonnegative(),
  objective_scale: z.number().int().positive(),
  category_counts: z.object({
    shade_structure: z.number().int().nonnegative(),
    tree_canopy: z.number().int().nonnegative(),
    cool_pavement: z.number().int().nonnegative(),
  }),
  equity_summary: z.object({
    mean_selected_vulnerability_score: z.number().min(0).max(1).nullable(),
    score_sum: z.number().nonnegative(),
    note: z.string(),
  }),
});
export type Portfolio = z.infer<typeof portfolioSchema>;

export const explanationSchema = z.object({
  mode: z.enum(["template", "openrouter"]),
  model: z.string().nullable(),
  fallback_reason: z.string().nullable(),
  site_id: z.string().min(1),
  candidate_id: z.string().min(1),
  budget_usd: z.number().int().positive(),
  summary: z.string().min(80),
  why_selected: z.array(z.string().min(1)).min(5),
  limitations: z.array(z.string().min(1)).min(3),
  evidence: z.array(evidenceSchema).min(5),
});
export type Explanation = z.infer<typeof explanationSchema>;

const interventionSchema = z.object({
  id: z.enum(["shade_structure", "tree_canopy", "cool_pavement"]),
  label: z.string(),
  description: z.string(),
  applicability: z.object({
    eligible_site_types: z.array(z.string()),
    screening_rule: z.string(),
    preconstruction_checks: z.array(z.string()),
    exclusion_rule: z.string(),
  }),
  planning_cost: z.object({
    estimate_usd: z.number().int().positive(),
    low_usd: z.number().int().positive(),
    high_usd: z.number().int().positive(),
    unit: z.string(),
    basis: z.string(),
    source_ids: z.array(z.string()),
  }),
  benefit_evidence: z.object({
    kind: z.string(),
    qualitative_benefit: z.string(),
    transfer_limit: z.string(),
    source_ids: z.array(z.string()),
  }),
  uncertainty: z.object({
    level: z.string(),
    summary: z.string(),
    factors: z.array(z.string()),
  }),
  lifespan_maintenance: z.object({
    expected_lifespan: z.string(),
    maintenance_note: z.string(),
    source_ids: z.array(z.string()),
  }),
});
export type Intervention = z.infer<typeof interventionSchema>;

const tileSchema = z.object({
  tile_id: z.string(),
  geometry: polygonGeometrySchema,
  heat: z.object({
    average_temperature_c: z.number(),
    persistence_hours: z.number().nonnegative(),
    exceedance_hours: z.number().nonnegative(),
    peak_heat_hour_utc: z.number().int().min(0).max(23),
    temperature_score: z.number().min(0).max(1),
    persistence_score: z.number().min(0).max(1),
    exceedance_score: z.number().min(0).max(1),
  }),
  exposure: z.object({
    transit_stop_count: z.number().int().nonnegative(),
    published_patronage_activity: z.number().nonnegative().nullable(),
    poi_count: z.number().int().nonnegative(),
  }),
  vulnerability: z.object({
    children_rate: z.number().nullable(),
    older_adult_rate: z.number().nullable(),
    poverty_rate: z.number().nullable(),
    no_vehicle_rate: z.number().nullable(),
  }),
  scores: z.object({
    heat: z.number().min(0).max(1),
    exposure: z.number().min(0).max(1),
    vulnerability: z.number().min(0).max(1),
    cooling_opportunity: z.number().min(0).max(1),
    priority: z.number().min(0).max(1),
  }),
  missing_fields: z.array(z.string()),
});

export const siteSchema = z.object({
  site_id: z.string(),
  site_name: z.string(),
  geometry: geometrySchema,
  street_view_evidence: z.object({
    site_id: z.string(),
    coordinates: z.object({ latitude: z.number(), longitude: z.number() }),
    frames: z.array(z.object({
      direction: z.enum(["front", "back"]),
      image_date: z.string(),
      original_image_available: z.boolean(),
      segmented_image_available: z.boolean(),
      segments: z.array(z.object({ label: z.string(), percentage: z.number().min(0).max(100) })),
      metrics: z.object({
        tree_pct: z.number().min(0).max(100).nullable(),
        grass_pct: z.number().min(0).max(100).nullable(),
        sky_pct: z.number().min(0).max(100).nullable(),
        road_pct: z.number().min(0).max(100).nullable(),
        sidewalk_pct: z.number().min(0).max(100).nullable(),
        building_pct: z.number().min(0).max(100).nullable(),
      }),
    })).min(1).max(2),
    aggregate: z.object({
      view_count: z.number().int().min(1).max(2),
      metrics: z.object({
        tree_pct: z.number().min(0).max(100).nullable(),
        grass_pct: z.number().min(0).max(100).nullable(),
        sky_pct: z.number().min(0).max(100).nullable(),
        road_pct: z.number().min(0).max(100).nullable(),
        sidewalk_pct: z.number().min(0).max(100).nullable(),
        building_pct: z.number().min(0).max(100).nullable(),
      }),
      contributing_views: z.object({
        tree_pct: z.number().int().min(0).max(2),
        grass_pct: z.number().int().min(0).max(2),
        sky_pct: z.number().int().min(0).max(2),
        road_pct: z.number().int().min(0).max(2),
        sidewalk_pct: z.number().int().min(0).max(2),
        building_pct: z.number().int().min(0).max(2),
      }),
    }),
    street_context_confidence: z.object({
      score: z.number().min(0).max(1),
      usable_view_count: z.number().int().min(0).max(2),
      oldest_image_age_days: z.number().int().nonnegative(),
      components: z.object({
        usable_views: z.number().min(0).max(1),
        imagery_availability: z.number().min(0).max(1),
        imagery_age: z.number().min(0).max(1),
        segmentation_completeness: z.number().min(0).max(1),
      }),
    }),
    shade_intervention_evidence: z.object({
      score: z.number().min(0).max(1),
      open_sky_context: z.number().min(0).max(1).nullable(),
      low_tree_context: z.number().min(0).max(1).nullable(),
      street_context_confidence: z.number().min(0).max(1),
      limitation: z.string().min(1),
    }),
  }).nullable(),
  options: z.array(
    z.object({ candidate: candidateSchema, tile: tileSchema, intervention: interventionSchema }),
  ).min(1),
});
export type Site = z.infer<typeof siteSchema>;

export const streetViewContextSchema = z.object({
  site_id: z.string().min(1),
  available: z.boolean(),
  image_date: z.string().nullable(),
  original_image_url: z.string().nullable(),
  segmented_image_url: z.string().nullable(),
  segments: z.record(z.string(), z.number().min(0).max(100)),
  source_label: z.string().min(1),
  source_url: z.url(),
  limitation: z.string().min(1),
});
export type StreetViewContext = z.infer<typeof streetViewContextSchema>;

export const methodologySchema = z.object({
  version: z.literal("1.0"),
  scoring: z.object({
    version: z.string(),
    priority_weights: z.record(z.string(), z.number()),
    heat_weights: z.object({
      temperature: z.number().min(0).max(1),
      persistence: z.number().min(0).max(1),
      exceedance: z.number().min(0).max(1),
    }),
    missing_strategy: z.string(),
    point_join_note: z.string(),
  }),
  heat_provenance: z.object({
    source: z.literal("FortyGuard Heatmap API"),
    source_url: z.url(),
    active_analysis_date: z.string(),
    exceedance_analysis_date: z.string(),
    exceedance_threshold_c: z.number(),
    exceedance_direction: z.enum(["above", "below"]),
    exceedance_request_hash: z.string().regex(/^[0-9a-f]{64}$/),
    exceedance_activity_id: z.string().min(1),
    exceedance_artifact_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    observed_credit_delta: z.number().int().nonnegative(),
    limitation: z.string().min(40),
  }),
  peak_hour_provenance: z.object({
    source: z.literal("FortyGuard Heatmap API"),
    source_url: z.url(),
    analysis_date: z.string(),
    timezone: z.literal("UTC"),
    request_hash: z.string().regex(/^[0-9a-f]{64}$/),
    activity_id: z.string().min(1),
    artifact_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    observed_credit_delta: z.number().int().nonnegative(),
    limitation: z.string().min(40),
  }),
  candidate_generation: z.object({
    screening_score_note: z.string(),
    representative_tile_rule: z.string(),
  }),
  optimization: z.object({
    budget_presets_usd: z.array(z.number().int().positive()),
    custom_budget_min_usd: z.number().int().positive(),
    custom_budget_max_usd: z.number().int().positive(),
    determinism_note: z.string(),
    objective_note: z.string(),
    equity_note: z.string(),
  }),
  interventions: z.object({
    cost_basis: z.object({ disclaimer: z.string() }),
    sources: z.array(
      z.object({
        id: z.string(),
        title: z.string(),
        publisher: z.string(),
        url: z.string().url(),
        published_at: z.string().nullable(),
        retrieved_at: z.string(),
        supports: z.array(z.string()),
      }),
    ),
    interventions: z.array(interventionSchema),
  }),
  limitations: z.array(z.string()).min(1),
});
export type Methodology = z.infer<typeof methodologySchema>;

export const dataStatusSchema = z.object({
  mode: z.enum(["cached_demo", "live_refreshed"]),
  external_calls_on_read: z.literal(false),
  refresh_available: z.boolean(),
  explanation_mode: z.enum(["template", "openrouter"]),
  heat_data_date: z.string(),
  heat_data_generated_at: z.string(),
  public_data_retrieved_at: z.string(),
  capabilities_evaluated_at: z.string(),
  credits: z.object({
    total: z.number().int().positive(),
    used: z.number().int().nonnegative(),
    remaining: z.number().int().nonnegative(),
    hard_reserve: z.number().int().nonnegative(),
  }),
  capabilities: z.array(z.unknown()),
  layers: z.array(layerNameSchema),
  candidate_count: z.number().int().min(20),
  candidate_source_artifacts: z.array(z.unknown()),
});
export type DataStatus = z.infer<typeof dataStatusSchema>;

export const refreshStatusSchema = z.object({
  state: z.enum(["idle", "running", "completed", "failed", "unavailable"]),
  message: z.string().min(1),
  requested_date: z.string().nullable(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  estimated_credit_cost: z.number().int().nonnegative().nullable(),
  credits_remaining: z.number().int().nonnegative().nullable(),
  hard_reserve: z.number().int().min(500_000),
});
export type RefreshStatus = z.infer<typeof refreshStatusSchema>;

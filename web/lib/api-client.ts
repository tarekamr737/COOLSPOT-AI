import type { ZodType } from "zod";

import {
  candidateListSchema,
  dataStatusSchema,
  explanationSchema,
  layerResponseSchema,
  methodologySchema,
  pilotSchema,
  portfolioSchema,
  refreshStatusSchema,
  siteSchema,
  streetViewContextSchema,
  type LayerName,
  type ScoringPreset,
} from "./api-schemas";

const API_ROOT = "/api/coolspot";

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // Preserve a non-JSON upstream message.
    }
    throw new Error(detail || `COOLSPOT API returned ${response.status}`);
  }
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new Error("The COOLSPOT API returned data that does not match the expected contract.");
  }
  return parsed.data;
}

export const getPilot = () => request("/pilot", pilotSchema);
export const getCandidates = () => request("/candidates", candidateListSchema);
export const getDataStatus = () => request("/data-status", dataStatusSchema);
export const getMethodology = () => request("/methodology", methodologySchema);
export const getLayer = (layer: LayerName) =>
  request(`/layers/${encodeURIComponent(layer)}`, layerResponseSchema);
export const getSite = (siteId: string) =>
  request(`/sites/${encodeURIComponent(siteId)}`, siteSchema);
export const getStreetView = (siteId: string) =>
  request(`/sites/${encodeURIComponent(siteId)}/street-view`, streetViewContextSchema);
export const optimize = (budgetUsd: number, scoringPreset: ScoringPreset = "balanced") =>
  request("/optimize", portfolioSchema, {
    method: "POST",
    body: JSON.stringify({ budget_usd: budgetUsd, scoring_preset: scoringPreset }),
  });
export const getExplanation = (siteId: string, candidateId: string, budgetUsd: number, scoringPreset: ScoringPreset = "balanced", regenerate = false) =>
  request(`/sites/${encodeURIComponent(siteId)}/explanation`, explanationSchema, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, budget_usd: budgetUsd, scoring_preset: scoringPreset, regenerate }),
  });
export const getRefreshStatus = () => request("/refresh/status", refreshStatusSchema);
export const startRefresh = (analysisDate: string, token: string) =>
  request("/refresh", refreshStatusSchema, {
    method: "POST",
    body: JSON.stringify({ analysis_date: analysisDate }),
    headers: { "X-Refresh-Token": token },
  });

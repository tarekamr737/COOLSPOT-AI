import type { ZodType } from "zod";

import {
  candidateListSchema,
  dataStatusSchema,
  layerResponseSchema,
  methodologySchema,
  pilotSchema,
  portfolioSchema,
  siteSchema,
  type LayerName,
} from "./api-schemas";

const API_ROOT = "/api/coolspot";

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `COOLSPOT API returned ${response.status}`);
  }
  return schema.parse(await response.json());
}

export const getPilot = () => request("/pilot", pilotSchema);
export const getCandidates = () => request("/candidates", candidateListSchema);
export const getDataStatus = () => request("/data-status", dataStatusSchema);
export const getMethodology = () => request("/methodology", methodologySchema);
export const getLayer = (layer: LayerName) =>
  request(`/layers/${encodeURIComponent(layer)}`, layerResponseSchema);
export const getSite = (siteId: string) =>
  request(`/sites/${encodeURIComponent(siteId)}`, siteSchema);
export const optimize = (budgetUsd: number) =>
  request("/optimize", portfolioSchema, {
    method: "POST",
    body: JSON.stringify({ budget_usd: budgetUsd }),
  });

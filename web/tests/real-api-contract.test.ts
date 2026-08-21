import { describe, expect, it } from "vitest";

import {
  candidateListSchema,
  dataStatusSchema,
  layerNames,
  layerResponseSchema,
  methodologySchema,
  pilotSchema,
  portfolioSchema,
  siteSchema,
} from "@/lib/api-schemas";

const apiUrl = process.env.COOLSPOT_API_TEST_URL;

async function json(path: string, init?: RequestInit) {
  const response = await fetch(`${apiUrl}${path}`, init);
  expect(response.status).toBe(200);
  return response.json();
}

describe.skipIf(!apiUrl)("real FastAPI contracts", () => {
  it("validates every response consumed by the planning UI", async () => {
    const [pilotValue, candidatesValue, statusValue, methodologyValue, ...layerValues] =
      await Promise.all([
        json("/v1/pilot"),
        json("/v1/candidates"),
        json("/v1/data-status"),
        json("/v1/methodology"),
        ...layerNames.map((layer) => json(`/v1/layers/${layer}`)),
      ]);

    const pilot = pilotSchema.parse(pilotValue);
    const candidates = candidateListSchema.parse(candidatesValue);
    dataStatusSchema.parse(statusValue);
    methodologySchema.parse(methodologyValue);
    layerValues.forEach((value) => layerResponseSchema.parse(value));

    const portfolio = portfolioSchema.parse(
      await json("/v1/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget_usd: pilot.default_budget_usd }),
      }),
    );
    const selected = candidates.candidates.find((candidate) =>
      portfolio.selected_candidate_ids.includes(candidate.id),
    );
    expect(selected).toBeDefined();
    siteSchema.parse(await json(`/v1/sites/${encodeURIComponent(selected!.site_id)}`));
  });
});

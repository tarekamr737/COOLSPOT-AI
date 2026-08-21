import { expect, test } from "@playwright/test";

type DataStatus = {
  external_calls_on_read: false;
  credits: { used: number; remaining: number };
};

test("golden planning path re-optimizes from cached data without FortyGuard calls", async ({ page }) => {
  const requestUrls: string[] = [];
  const optimizeBodies: string[] = [];

  page.on("request", (request) => {
    requestUrls.push(request.url());
    if (request.url().endsWith("/api/coolspot/optimize")) {
      optimizeBodies.push(request.postData() ?? "");
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Pacoima cooling investment map" })).toBeAttached();
  await expect(page.getByRole("region", { name: "Interactive Pacoima heat layer map" })).toHaveAttribute(
    "data-map-state",
    "ready",
  );
  await expect(page.getByLabel("Data freshness status")).toContainText("CACHED ANALYSIS");
  await expect(page.getByRole("button", { name: "Refresh data" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "$500,000 budget" })).toBeVisible();
  await expect(page.getByText("10 sites", { exact: true })).toBeVisible();

  const beforeResponse = await page.request.get("/api/coolspot/data-status");
  expect(beforeResponse.ok()).toBe(true);
  const before = (await beforeResponse.json()) as DataStatus;
  expect(before.external_calls_on_read).toBe(false);
  expect(before.credits).toMatchObject({ used: 8_440, remaining: 1_991_560 });

  const persistence = page.getByRole("button", { name: "Persistence" });
  await persistence.click();
  await expect(persistence).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("2,001 tiles", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "$1M", exact: true }).click();
  await expect(page.getByRole("heading", { name: "$1,000,000 budget" })).toBeVisible();
  await expect(page.getByText("20 sites", { exact: true })).toBeVisible();

  const recommendationButtons = page
    .getByRole("complementary", { name: "Ranked recommendations" })
    .getByRole("button");
  const secondRecommendation = recommendationButtons.nth(1);
  const secondSiteName = (await secondRecommendation.locator("strong").textContent())?.trim();
  expect(secondSiteName).toBeTruthy();
  await secondRecommendation.click();
  await expect(page.getByRole("heading", { level: 2, name: secondSiteName! })).toBeVisible();

  await page.getByText("Methodology & limitations", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Source links" })).toBeVisible();

  await page.getByRole("button", { name: "Ask AI", exact: true }).click();
  await expect(page.getByText(/Deterministic fallback/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence used" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Limits" })).toBeVisible();

  const afterResponse = await page.request.get("/api/coolspot/data-status");
  expect(afterResponse.ok()).toBe(true);
  const after = (await afterResponse.json()) as DataStatus;
  expect(after.external_calls_on_read).toBe(false);
  expect(after.credits).toEqual(before.credits);

  expect(optimizeBodies.some((body) => body.includes('"budget_usd":500000'))).toBe(true);
  expect(optimizeBodies.some((body) => body.includes('"budget_usd":1000000'))).toBe(true);
  expect(requestUrls.filter((url) => /fortyguard/i.test(url))).toEqual([]);
});

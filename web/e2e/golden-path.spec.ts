import { expect, test } from "@playwright/test";

type DataStatus = {
  mode: "cached_demo" | "live_refreshed";
  external_calls_on_read: false;
  credits: { total: number; used: number; remaining: number; hard_reserve: number };
};

test("golden planning path re-optimizes from cached data without FortyGuard calls", async ({ page }) => {
  test.setTimeout(90_000);
  const requestUrls: string[] = [];
  const optimizeBodies: string[] = [];

  page.on("request", (request) => {
    requestUrls.push(request.url());
    if (request.url().endsWith("/api/coolspot/optimize")) {
      optimizeBodies.push(request.postData() ?? "");
    }
  });

  await page.goto("/");
  const skipTour = page.getByRole("button", { name: "Skip tour" });
  await expect(skipTour).toBeVisible();
  await skipTour.click();
  await expect(page.getByRole("heading", { name: "Pacoima cooling investment map" })).toBeAttached();
  await expect(page.getByRole("region", { name: "Interactive Pacoima heat layer map" })).toHaveAttribute(
    "data-map-state",
    "ready",
  );
  await expect(page.getByLabel("Data freshness status")).toContainText(/CACHED ANALYSIS|LIVE REFRESHED/);
  await expect(page.getByRole("button", { name: "Refresh data" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "$500,000 budget" })).toBeVisible();
  await expect(page.getByText("10 sites", { exact: true })).toBeVisible();

  const beforeResponse = await page.request.get("/api/coolspot/data-status");
  expect(beforeResponse.ok()).toBe(true);
  const before = (await beforeResponse.json()) as DataStatus;
  expect(before.external_calls_on_read).toBe(false);
  expect(before.credits.used).toBeGreaterThanOrEqual(8_440);
  expect(before.credits.remaining).toBe(before.credits.total - before.credits.used);
  expect(before.credits.remaining).toBeGreaterThanOrEqual(before.credits.hard_reserve);

  const persistence = page.getByRole("button", { name: "Persistence" });
  await persistence.click();
  await expect(persistence).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("2,001 tiles", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "$1M", exact: true }).click();
  await expect(page.getByRole("heading", { name: "$1,000,000 budget" })).toBeVisible();
  await expect(page.getByText("20 sites", { exact: true })).toBeVisible();

  await page.getByLabel("Planning priority").selectOption("exposure_first");
  await expect(page.getByLabel("Planning priority")).toHaveValue("exposure_first");
  await expect(page.getByText("H 30 · E 40 · V 20 · O 10")).toBeVisible();

  const recommendationButtons = page
    .getByRole("complementary", { name: "Ranked recommendations" })
    .getByRole("button");
  const secondRecommendation = recommendationButtons.nth(1);
  const secondSiteName = (await secondRecommendation.locator("strong").textContent())?.trim();
  expect(secondSiteName).toBeTruthy();
  await secondRecommendation.click();
  const streetContext = page.getByRole("region", { name: `Street context for ${secondSiteName!}` });
  await expect(streetContext).toBeVisible();
  const segmentedImage = streetContext.getByRole("img", { name: `FortyGuard segmented street view for ${secondSiteName!}` });
  await expect(segmentedImage).toBeVisible();
  await expect.poll(() => segmentedImage.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await streetContext.getByRole("button", { name: "Street image" }).click();
  const streetImage = streetContext.getByRole("img", { name: `Street view for ${secondSiteName!}` });
  await expect(streetImage).toBeVisible();
  await expect.poll(() => streetImage.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Close street context" }).click();
  await expect(page.getByRole("heading", { level: 2, name: secondSiteName! })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Weather conditions at this finalist" })).toBeVisible();
  await expect(page.getByText("Apparent temperature", { exact: true })).toBeVisible();
  await expect(page.getByText("Relative humidity", { exact: true })).toBeVisible();

  await page.getByText("Methodology & limitations", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Source links" })).toBeVisible();

  await page.getByRole("button", { name: "Ask AI", exact: true }).click();
  await expect(page.getByText(/grounded evidence only|Deterministic fallback/)).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole("heading", { name: "Sources used" })).toBeVisible();
  await page.getByText("Evidence and limitations", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Evidence used" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Limits" })).toBeVisible();

  const afterResponse = await page.request.get("/api/coolspot/data-status");
  expect(afterResponse.ok()).toBe(true);
  const after = (await afterResponse.json()) as DataStatus;
  expect(after.external_calls_on_read).toBe(false);
  expect(after.credits).toEqual(before.credits);

  expect(optimizeBodies.some((body) => body.includes('"budget_usd":500000'))).toBe(true);
  expect(optimizeBodies.some((body) => body.includes('"budget_usd":1000000'))).toBe(true);
  expect(optimizeBodies.some((body) => body.includes('"scoring_preset":"exposure_first"'))).toBe(true);
  expect(requestUrls.filter((url) => /fortyguard/i.test(url))).toEqual([]);
});

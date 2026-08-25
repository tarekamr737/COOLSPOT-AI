import { expect, test, type Locator, type Page } from "@playwright/test";

async function expectInsideViewport(page: Page, locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test("map-led workflow remains usable at narrow portrait and landscape widths", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto("/");
  const skipTour = page.getByRole("button", { name: "Skip tour" });
  if (await skipTour.isVisible()) await skipTour.click();

  await expectNoHorizontalOverflow(page);
  await expectInsideViewport(page, page.getByRole("button", { name: "How it works" }));
  await expectInsideViewport(page, page.getByRole("button", { name: "Refresh data" }));
  await expect(page.getByRole("button", { name: "Refresh data" })).toHaveCSS("min-height", "44px");

  const mapTop = await page.getByRole("heading", { name: "Pacoima cooling investment map" }).evaluate((el) => el.getBoundingClientRect().top);
  const recommendationsTop = await page.getByRole("heading", { name: "Ranked recommendations" }).evaluate((el) => el.getBoundingClientRect().top);
  const evidenceTop = await page.getByRole("complementary", { name: "Pacoima Early Education Center" }).evaluate((el) => el.getBoundingClientRect().top);
  expect(mapTop).toBeLessThan(recommendationsTop);
  expect(recommendationsTop).toBeLessThan(evidenceTop);

  await page.setViewportSize({ width: 844, height: 390 });
  await expectNoHorizontalOverflow(page);
  await expectInsideViewport(page, page.getByRole("combobox", { name: "Planning priority" }));
});

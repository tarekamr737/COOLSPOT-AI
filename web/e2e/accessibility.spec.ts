import { expect, test } from "@playwright/test";

test("evidence semantics and keyboard bypass remain accessible", async ({ page }) => {
  await page.goto("/");
  const skipTour = page.getByRole("button", { name: "Skip tour" });
  if (await skipTour.isVisible()) await skipTour.click();

  const meter = page.getByRole("meter", { name: "Evidence confidence" });
  await expect(meter).toHaveAttribute("aria-valuemin", "0");
  await expect(meter).toHaveAttribute("aria-valuemax", "1");
  await expect(meter).toHaveAttribute("aria-valuenow", /^0(?:\.\d+)?$/);

  const provenanceLink = page.getByRole("link", { name: "FortyGuard source" }).first();
  await expect(provenanceLink).toHaveCSS("text-decoration-line", "underline");

  const skipLink = page.getByRole("link", { name: "Skip to map workspace" });
  await skipLink.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#map-workspace")).toBeFocused();
});

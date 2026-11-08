import { test, expect } from "@playwright/test";

for (const width of [1280, 830, 320]) {
  test(`Inbox opens first and search stays inside its pane at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height:900 });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/");
    await expect(page.locator(".topbar-title")).toHaveText("Inbox");
    await expect(page.locator(".sidebar-nav .nav-btn").first()).toHaveText("Inbox");
    await expect(page.getByLabel("Navigate to page").locator("option").first()).toHaveAttribute("value", "email");
    const search = page.getByPlaceholder("Search emails…");
    await expect(search).toBeVisible();
    const pane = await page.locator(".email-sidebar").boundingBox();
    for (const control of [search, page.getByRole("button", { name:"Compose", exact:true }), page.locator(".email-toolbar-left")]) {
      const box = await control.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(pane.x);
      expect(box.x + box.width).toBeLessThanOrEqual(pane.x + pane.width);
    }
    await expect(page.locator(".email-item").first()).toBeVisible();
    await search.fill("Okafor");
    await expect(page.locator(".email-item")).toHaveCount(1);
    await page.locator(".email-item").click();
    await expect(page.locator(".email-detail-body")).toContainText("mid-December");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    await page.screenshot({ path:testInfo.outputPath(`inbox-${width}.png`), fullPage:true });
  });
}

import { test, expect } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`calendar avoids manual categories and duplicate event cards at ${width}px`, async ({ page }, testInfo) => {
    const events = ["quarterly_review", "goal_review"].map((type, index) => ({
      id: `TEST-${index}`, version: `v${index}`, client_id: "CLI-001", client_name: "Garcia Family",
      title: `Client discussion ${index + 1}`, date: "2026-11-12", start_time: `${14 + index}:00`,
      end_time: `${15 + index}:00`, starts_at: `2026-11-12T${14 + index}:00:00-05:00`,
      duration_minutes: 60, prep_required: true, type, focus: "Client priorities", location: "Office", notes: "Discuss client priorities",
    }));
    const state = { now: "2026-11-11T15:00:00-05:00", enabled: false, mode: "simulation", events, preparations: [], saved_meetings: [] };
    await page.route("**/api/meeting-preparations", route => route.fulfill({ json: state }));
    await page.route("**/api/calendar/events?*", route => route.fulfill({ json: events }));
    // Fail closed: this UI check must not generate briefs or mutate Calendar.
    await page.route("**/api/**", async route => {
      if (route.request().method() !== "GET") return route.abort();
      return route.fallback();
    });
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    if (width < 768) await page.getByLabel("Navigate to page").selectOption("calendar");
    else await page.getByRole("button", { name: "Calendar", exact: true }).click();
    await expect(page.locator(".cal-event-entry")).toHaveCount(2);
    await expect(page.locator(".cal-legend")).toHaveCount(0);
    await expect(page.locator(".cal-selected-event")).toHaveCount(0);
    const colors = await page.locator(".cal-event-entry").evaluateAll(nodes => nodes.map(node => getComputedStyle(node).backgroundColor));
    expect(new Set(colors).size).toBe(1);
    await page.getByRole("button", { name: "Edit event: Client discussion 1, 2026-11-12 at 14:00", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Edit Event" });
    await expect(dialog.getByLabel("Type", { exact: true })).toHaveCount(0);
    await expect(dialog.getByLabel("Title", { exact: true })).toHaveValue("Client discussion 1");
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.screenshot({ path: testInfo.outputPath("calendar-simplified.png"), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

import { test, expect } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`new meetings use the shared calendar editor at ${width}px`, async ({ page }, testInfo) => {
    const events = [];
    const state = { now: "2026-11-11T15:00:00-05:00", mode: "simulation", enabled: false, events, preparations: [] };
    let creations = 0;
    await page.route("**/api/meeting-preparations", route => route.fulfill({ json: state }));
    await page.route("**/api/calendar/events?*", route => route.fulfill({ json: events }));
    await page.route("**/api/calendar/events", async route => {
      expect(route.request().method()).toBe("POST");
      const fields = route.request().postDataJSON();
      expect(fields.type).toBeUndefined();
      creations += 1;
      const record = { ...fields, id: "NEW-MEETING", version: "v1", client_name: "Garcia Family",
        type: "general_meeting", prep_required: true, focus: fields.notes, starts_at: `${fields.date}T${fields.start_time}:00-05:00` };
      events.push(record);
      await route.fulfill({ json: record });
    });
    await page.route("**/api/briefings", route => route.abort());
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    if (width < 768) await page.getByLabel("Navigate to page").selectOption("meeting");
    else await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    await expect(page.getByRole("button", { name: "Prepare another meeting", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "New meeting", exact: true }).click();
    const editor = page.getByRole("dialog", { name: "New Event" });
    await editor.getByLabel("Title", { exact: true }).fill("Home funding discussion");
    await editor.getByLabel("Client", { exact: true }).selectOption("CLI-001");
    await editor.getByLabel("Date", { exact: true }).fill("2026-11-12");
    await editor.getByLabel("Start Time").fill("14:00");
    await editor.getByLabel("End Time").fill("15:00");
    await editor.getByLabel("Notes").fill("Confirm funding timeline");
    await editor.getByRole("button", { name: "Save", exact: true }).click();
    await expect(editor).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Scheduled preparation" })).toContainText("Home funding discussion");
    await expect(page.getByRole("region", { name: "Scheduled preparation" })).toContainText("Confirm funding timeline");
    await page.screenshot({ path: testInfo.outputPath("calendar-backed-meeting.png"), fullPage: true });
    if (width < 768) await page.getByLabel("Navigate to page").selectOption("calendar");
    else await page.getByRole("button", { name: "Calendar", exact: true }).first().click();
    await expect(page.getByRole("button", { name: "Edit event: Home funding discussion, 2026-11-12 at 14:00", exact: true })).toBeVisible();
    expect(creations).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

import { test, expect } from "@playwright/test";

for (const action of ["open prep", "save first"]) {
  test(`editing notes and choosing ${action} prepares from saved notes`, async ({ page }, testInfo) => {
    const event = { id: "EDIT-MEETING", client_id: "CLI-001", client_name: "Garcia Family", version: "v1",
      title: "Q4 Review: Garcia Family", date: "2026-11-12", start_time: "14:00", end_time: "15:00",
      starts_at: "2026-11-12T14:00:00-05:00", type: "quarterly_review", prep_required: true,
      notes: "Discuss retirement projections and 529 plan", focus: "Discuss retirement projections and 529 plan", duration_minutes: 60 };
    const job = { id: "OLD-JOB", event_id: event.id, version: "v1", status: "ready", mode: "simulation", brief_id: "OLD" };
    const state = { now: "2026-11-11T15:00:00-05:00", mode: "simulation", enabled: false, events: [event], preparations: [job] };
    let updates = 0;
    await page.route("**/api/meeting-preparations", route => route.fulfill({ json: state }));
    await page.route("**/api/calendar/events?*", route => route.fulfill({ json: [event] }));
    await page.route("**/api/calendar/events/EDIT-MEETING", async route => {
      expect(route.request().method()).toBe("PUT");
      const update = route.request().postDataJSON();
      expect(update.notes).toBe("Discuss retirement projections only");
      updates += 1;
      Object.assign(event, update, { version: "v2", focus: update.notes });
      Object.assign(job, { id: "NEW-JOB", version: "v2", status: "queued", brief_id: null });
      await route.fulfill({ json: event });
    });
    await page.route("**/api/meeting-preparations/events/EDIT-MEETING", route => route.fulfill({ json: job }));
    await page.goto("/");
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    await page.getByRole("button", { name: "Edit event: Q4 Review: Garcia Family, 2026-11-12 at 14:00", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Edit Event" });
    await dialog.getByRole("textbox", { name: "Notes", exact: true }).fill("Discuss retirement projections only");
    if (action === "open prep") {
      await dialog.getByRole("button", { name: /Meeting prep|Save & view prep/i }).click();
    } else {
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await page.getByRole("button", { name: "View meeting prep for Garcia Family on 2026-11-12", exact: true }).click();
    }
    await expect.poll(() => updates).toBe(1);
    await expect(page.getByRole("heading", { name: "Preparing your meeting brief", exact: true })).toBeVisible();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toHaveCount(0);
    Object.assign(job, { status: "ready", brief_id: "NEW" });
    await page.route("**/api/meeting-preparations/NEW-JOB/brief", route => route.fulfill({ json: {
      id: "NEW", client_id: event.client_id, client_name: event.client_name, calendar_event: { ...event },
      contact: "Synthetic client", meeting_date: event.date, meeting_time: event.start_time, focus: event.focus,
      mode: "simulation", sources: [{ id: "PROFILE", title: "Profile" }], news: [], sections: [{ id: "priorities", title: "Discussion Priorities",
        items: [{ id: "priority-1", title: "Confirm retirement plans", text: event.focus, why: "Meeting notes", question: "What changed?", source_ids: ["PROFILE"] }] }],
    } }));
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toHaveAttribute("data-brief-id", "NEW");
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Discuss retirement projections only");
    await page.screenshot({ path: testInfo.outputPath("saved-notes-preparation.png"), fullPage: true });
  });
}

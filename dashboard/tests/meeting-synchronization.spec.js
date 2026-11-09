import { test, expect } from "@playwright/test";

test("a Calendar edit replaces an open Copilot brief with current preparation", async ({ page }, testInfo) => {
  const event = { id: "MEETING", version: "v1", client_id: "CLI-001", client_name: "Garcia Family",
    title: "Original meeting", date: "2026-11-12", start_time: "14:00", starts_at: "2026-11-12T14:00:00-05:00",
    focus: "Original focus", duration_minutes: 60, prep_required: true };
  const makeBrief = (id, snapshot) => ({ id, client_id: snapshot.client_id, client_name: snapshot.client_name,
    calendar_event: { ...snapshot }, meeting_date: snapshot.date, meeting_time: snapshot.start_time, focus: snapshot.focus,
    contact: "Synthetic client", mode: "simulation", data_as_of: "2026-11-11", sources: [{ id: "PROFILE", title: "Profile" }], news: [],
    sections: [{ id: "priorities", title: "Discussion Priorities", items: [{ id: "priority-1", title: snapshot.focus,
      text: snapshot.focus, why: "Client priorities", question: "What changed?", source_ids: ["PROFILE"] }] }] });
  const old = makeBrief("OLD-BRIEF", event);
  const job = { id: "OLD-JOB", event_id: event.id, version: "v1", status: "ready", mode: "simulation", brief_id: old.id };
  const state = { now: "2026-11-11T15:00:00-05:00", mode: "simulation", enabled: false, events: [event], preparations: [job] };
  await page.route("**/api/meeting-preparations", route => route.fulfill({ json: state }));
  await page.route("**/api/chat", route => route.fulfill({ json: { response: "Your brief is ready.", intent: "meeting_briefing", brief: old, agents_used: [], steps: [] } }));
  await page.route("**/api/meeting-preparations/events/MEETING", route => route.fulfill({ json: job }));
  await page.route("**/api/meeting-preparations/NEW-JOB/brief", route => route.fulfill({ json: makeBrief("NEW-BRIEF", event) }));
  await page.goto("/");
  await page.getByRole("button", { name: "Copilot", exact: true }).click();
  await page.locator(".co-textarea").fill("Prepare my meeting");
  await page.locator(".co-send").click();
  await page.getByRole("button", { name: "Open Meeting Brief", exact: true }).click();
  const article = page.getByRole("article", { name: "Meeting briefing" });
  await expect(article).toHaveAttribute("data-brief-id", "OLD-BRIEF");
  Object.assign(event, { version: "v2", title: "Rescheduled meeting", start_time: "16:00",
    starts_at: "2026-11-12T16:00:00-05:00", focus: "Updated funding priorities" });
  Object.assign(job, { id: "NEW-JOB", version: "v2", status: "queued", brief_id: null });
  await expect(article).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Preparing your meeting brief", exact: true })).toBeVisible();
  await expect(page.locator(".calendar-meeting-loading")).toContainText("Rescheduled meeting");
  Object.assign(job, { status: "ready", brief_id: "NEW-BRIEF" });
  await expect(article).toHaveAttribute("data-brief-id", "NEW-BRIEF");
  await expect(article).toContainText("Updated funding priorities");
  await expect(article).not.toContainText("Original focus");
  await page.screenshot({ path: testInfo.outputPath("updated-meeting-brief.png"), fullPage: true });
});

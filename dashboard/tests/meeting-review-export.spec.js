import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function preparedFixture(page, request, purpose) {
  const fields = { client_id: "CLI-004", title: `Part B audit: ${purpose}`, date: "2026-11-24",
    start_time: "14:00", end_time: "15:00", notes: `Confirm home funding questions for ${purpose}` };
  const created = await request.post("/api/calendar/events", { data: fields });
  expect(created.ok()).toBe(true);
  const event = await created.json();
  try {
    const prepared = await request.post("/api/briefings", { data: { client_id: event.client_id, calendar_event_id: event.id,
      meeting_date: event.date, meeting_time: event.start_time, focus: event.notes, mode: "simulation" } });
    expect(prepared.ok()).toBe(true);
    await page.goto("/");
    await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    await page.getByRole("complementary", { name: "Client meetings" }).getByRole("button", { name: "All meetings", exact: true }).click();
    await page.getByRole("button", { name: "Open preparation for Okafor Family on 2026-11-24", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toBeVisible();
    return event;
  } catch (error) { await request.delete(`/api/calendar/events/${event.id}`); throw error; }
}

test("automatic check failures block review until saving succeeds", async ({ page, request }, testInfo) => {
  const event = await preparedFixture(page, request, "automatic review");
  try {
    let checks = 0;
    await page.route("**/api/meeting-learning/briefs/*/edits", async route => {
      const response = await route.fetch();
      const state = await response.json();
      if (++checks === 1) state.brief.workflow.quality = { verdict: "unavailable", findings: [] };
      await route.fulfill({ response, json: state });
    });
    const process = page.locator("summary").filter({ hasText: "Preparation details" });
    await expect(page.getByRole("button", { name: "Check draft", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Edit prep", exact: true }).click();
    await page.getByLabel("Client Overview: item details").first().fill("Advisor question: confirm current priorities.");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(process).toContainText("Automatic checks need attention");
    await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath("automatic-check-unavailable.png"), fullPage: true });
    await page.getByRole("button", { name: "Edit prep", exact: true }).click();
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(process).toContainText("Check: pass");
    await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeEnabled();
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

test("PDF download exports the selected calendar briefing", async ({ page, request }, testInfo) => {
  const event = await preparedFixture(page, request, "PDF download");
  try {
    const pending = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download PDF", exact: true }).click();
    const download = await pending;
    expect(download.suggestedFilename()).toBe("meeting-brief-CLI-004-2026-11-24.pdf");
    const path = testInfo.outputPath("meeting-brief.pdf");
    await download.saveAs(path);
    const bytes = await readFile(path);
    expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
    expect(bytes.length).toBeGreaterThan(500);
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

test("saved edits and automatic check results survive reopening", async ({ page, request }) => {
  const event = await preparedFixture(page, request, "saved editing");
  try {
    await page.getByRole("button", { name: "Edit prep", exact: true }).click();
    await page.getByLabel("Client Overview: item details").first().fill("Advisor question: confirm current priorities.");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("summary").filter({ hasText: "Preparation details" })).toContainText("Check: pass");
    await page.reload();
    await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    await page.getByRole("complementary", { name: "Client meetings" }).getByRole("button", { name: "All meetings", exact: true }).click();
    await page.getByRole("button", { name: "Open preparation for Okafor Family on 2026-11-24", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Advisor question: confirm current priorities.");
    await expect(page.locator("summary").filter({ hasText: "Preparation details" })).toContainText("Check: pass");
    await page.getByText("Feedback & edit history", { exact: true }).click();
    await expect(page.getByRole("region", { name: "Learning from your feedback" })).toContainText("Advisor edited");
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

test("feedback saves in one click without opening a form", async ({ page, request }) => {
  const event = await preparedFixture(page, request, "one-click feedback");
  try {
    await page.getByRole("link", { name: "Give feedback", exact: true }).click();
    const feedback = page.getByRole("region", { name: "Meeting preparation feedback" });
    for (const [label, rating] of [["Helpful", "helpful"], ["Needs improvement", "needs_work"]]) {
      const saved = page.waitForResponse(response => response.url().endsWith("/feedback") && response.request().method() === "POST");
      await feedback.getByRole("button", { name: label, exact: true }).click();
      const response = await saved;
      expect(response.ok()).toBe(true);
      expect((await response.json()).feedback.rating).toBe(rating);
      await expect(feedback.getByRole("button", { name: label, exact: true })).toHaveAttribute("aria-pressed", "true");
      await expect(feedback.getByRole("status")).toHaveText("Feedback saved");
      await expect(feedback.locator("form, textarea, select")).toHaveCount(0);
      await expect(feedback.getByRole("button", { name: "Save feedback", exact: true })).toHaveCount(0);
    }
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

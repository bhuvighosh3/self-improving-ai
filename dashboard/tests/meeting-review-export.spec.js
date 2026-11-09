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

test("review unavailable removes pass status until a successful retry", async ({ page, request }, testInfo) => {
  const event = await preparedFixture(page, request, "review failure");
  try {
    let checks = 0;
    await page.route("**/api/briefings/check", route => {
      checks += 1;
      return checks === 1 ? route.fulfill({ status: 502, json: { detail: "Quality reviewer unavailable; draft was not approved." } })
        : route.fulfill({ json: { verdict: "pass", findings: [], semantic_support: "manual_advisor_review_required_offline" } });
    });
    const process = page.locator("summary").filter({ hasText: "Preparation process" });
    await expect(process).toContainText("Check: pass");
    await page.getByRole("button", { name: "Check draft", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Quality reviewer unavailable");
    await expect(process).toContainText("Check unavailable");
    await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath("review-unavailable.png"), fullPage: true });
    await page.getByRole("button", { name: "Check draft", exact: true }).click();
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

test("edited briefing retains its recheck status after reopening", async ({ page, request }) => {
  const event = await preparedFixture(page, request, "edited review");
  const reopen = async () => {
    await page.reload();
    await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    await page.getByRole("complementary", { name: "Client meetings" }).getByRole("button", { name: "All meetings", exact: true }).click();
    await page.getByRole("button", { name: "Open preparation for Okafor Family on 2026-11-24", exact: true }).click();
  };
  try {
    const process = page.locator("summary").filter({ hasText: "Preparation process" });
    await page.getByRole("button", { name: "Edit draft", exact: true }).click();
    await page.getByLabel("Client Overview: item details").first().fill("Advisor revised the meeting context.");
    await page.getByRole("button", { name: "Done editing", exact: true }).click();
    await expect(process).toContainText("recheck required");
    await reopen();
    await expect(process).toContainText("recheck required");
    await page.route("**/api/briefings/check", route => route.fulfill({ json: { verdict: "revise", findings: [], semantic_support: "manual_advisor_review_required_offline" } }));
    await page.getByRole("button", { name: "Check draft", exact: true }).click();
    await expect(process).toContainText("Check: revise");
    await reopen();
    await expect(process).toContainText("Check: revise");
    await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

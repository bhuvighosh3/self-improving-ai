import { test, expect } from "@playwright/test";

const state = async request => (await request.get("/api/meeting-preparations")).json();

for (const width of [1280, 390]) {
  test(`shared calendar opens and reviews Part B preparation at ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(async () => (await state(request)).processing).toBe(false);
    expect((await request.post("/api/meeting-preparations/simulation", { data: { action: "reset" } })).ok()).toBe(true);
    await expect.poll(async () => (await state(request)).preparations.filter(job => job.status === "ready").length).toBe(1);
    await page.goto("/");
    const calendar = page.getByRole("region", { name: "Client calendar" });
    await expect(calendar).toBeVisible();
    await expect(page.locator(".cal-month-label")).toHaveText("November 2026");
    await expect(page.locator(".cal-weekday")).toHaveCount(7);
    await expect(page.locator(".cal-event-entry")).toHaveCount(5);
    const notice = page.getByRole("dialog");
    await expect(notice).toContainText("Your brief for Garcia Family is ready");
    await page.screenshot({ path: testInfo.outputPath("shared-calendar-notice.png"), fullPage: true });
    await notice.getByRole("button", { name: "View meeting prep", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Garcia Family");
    await expect(page.getByRole("region", { name: "Meeting at a glance" })).toBeVisible();
    await page.getByRole("button", { name: "Back to calendar", exact: true }).click();
    await expect(calendar).toBeVisible();
    await expect(notice).toHaveCount(0);
    await expect(page.locator(".cal-event-entry")).toHaveCount(5);
    await expect(page.locator(".calendar-next-meeting")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("shared-calendar.png"), fullPage: true });
    await page.getByRole("button", { name: "View meeting prep for Okafor Family on 2026-11-20", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Okafor Family");
    await expect(page.locator(".meeting-section")).toHaveCount(6);
    await page.getByRole("button", { name: "Mark as reviewed", exact: true }).click();
    await expect(page.locator(".calendar-prep-context .chip")).toHaveText("Reviewed");
    await page.screenshot({ path: testInfo.outputPath("shared-meeting-brief.png"), fullPage: true });
    if (width < 768) await page.getByRole("button", { name: "All meetings", exact: true }).click();
    await page.getByLabel("Search client meetings").fill("Chen");
    await expect(page.locator(".prep-meeting-row")).toHaveCount(2);
    await page.getByRole("button", { name: "Open preparation for Chen Household on 2026-11-18", exact: true }).click();
    await expect(page.getByRole("region", { name: "Scheduled preparation" })).toContainText("24 hours before");
    await page.getByRole("button", { name: "Prepare early", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Chen Household");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await state(request)).preparations.filter(job => job.status === "ready")).toHaveLength(3);
    await request.post("/api/meeting-preparations/simulation", { data: { action: "pause" } });
  });
}

test("calendar editing validates dates and shares new meetings with preparation", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "+ New Event", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "New Event" });
  await dialog.getByLabel("Title", { exact: true }).fill("Integration review meeting");
  await dialog.getByLabel("Client", { exact: true }).selectOption("CLI-004");
  await dialog.getByLabel("Date", { exact: true }).fill("2026-11-21");
  await dialog.getByLabel("Start Time").fill("16:00");
  await dialog.getByLabel("End Time").fill("15:00");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await dialog.getByLabel("End Time").fill("17:00");
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const records = await (await request.get("/api/calendar/events?year=2026&month=11")).json();
  const event = records.find(event => event.title === "Integration review meeting");
  expect(event).toBeTruthy();
  try {
    await expect(page.getByRole("button", { name: "16:00 Integration review meeting", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "View meeting prep for Okafor Family on 2026-11-21", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toBeVisible();
    await expect(page.locator(".calendar-prep-context")).toContainText("Integration review meeting");
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

test("teammate Inbox retains read and archive operations", async ({ page, request }, testInfo) => {
  await request.patch("/api/email/messages/EML-a3b4c5d6", { data: { folder: "inbox" } });
  await page.goto("/");
  await page.getByRole("button", { name: "Inbox", exact: true }).click();
  await expect(page.locator(".email-simulation-note")).toContainText("Simulated Inbox");
  await page.locator(".email-item").filter({ hasText: "Down payment" }).click();
  await expect(page.locator(".email-detail-body")).toContainText("mid-December");
  await page.locator(".email-detail-actions").getByRole("button", { name: "Archive", exact: true }).click();
  await page.locator(".email-toolbar-left").getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.locator(".email-item").filter({ hasText: "Down payment" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("shared-inbox.png"), fullPage: true });
  await request.patch("/api/email/messages/EML-a3b4c5d6", { data: { folder: "inbox" } });
});

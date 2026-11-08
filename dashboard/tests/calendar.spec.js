import { test, expect } from "@playwright/test";

const state = async request => (await request.get("/api/meeting-preparations")).json();

async function openCalendar(page) {
  await page.goto("/");
  const mobileNav = page.getByLabel("Navigate to page");
  if (await mobileNav.isVisible()) await mobileNav.selectOption("calendar");
  else await page.locator(".sidebar-nav").getByRole("button", { name: "Calendar", exact: true }).click();
}

for (const width of [1280, 390]) {
  test(`shared calendar opens and reviews Part B preparation at ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(async () => (await state(request)).processing).toBe(false);
    expect((await request.post("/api/meeting-preparations/simulation", { data: { action: "reset" } })).ok()).toBe(true);
    await expect.poll(async () => (await state(request)).preparations.filter(job => job.status === "ready").length).toBe(1);
    await openCalendar(page);
    const calendar = page.getByRole("region", { name: "Client calendar" });
    await expect(calendar).toBeVisible();
    await expect(page.locator(".cal-week-label")).toHaveText("Nov 9 – 15, 2026");
    await expect(page.locator(".cal-day-heading")).toHaveCount(7);
    await expect(page.locator(".cal-event-entry")).toHaveCount(2);
    const notice = page.getByRole("dialog");
    await expect(notice).toContainText("Your brief for Garcia Family is ready");
    await page.screenshot({ path: testInfo.outputPath("shared-calendar-notice.png"), fullPage: true });
    await notice.getByRole("button", { name: "View meeting prep", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Garcia Family");
    await expect(page.getByRole("region", { name: "Meeting at a glance" })).toBeVisible();
    await page.getByRole("button", { name: "Back to calendar", exact: true }).click();
    await expect(calendar).toBeVisible();
    await expect(notice).toHaveCount(0);
    await expect(page.locator(".cal-event-entry")).toHaveCount(2);
    await expect(page.locator(".calendar-next-meeting")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("shared-calendar.png"), fullPage: true });
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await expect(page.locator(".cal-week-label")).toHaveText("Nov 16 – 22, 2026");
    await page.getByRole("button", { name: "Friday, November 20", exact: true }).click();
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
  await openCalendar(page);
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
    await page.getByRole("button", { name: "Next week", exact: true }).click();
    await page.getByRole("button", { name: "Saturday, November 21", exact: true }).click();
    await expect(page.getByRole("button", { name: "Edit event: Integration review meeting, 2026-11-21 at 16:00", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "View meeting prep for Okafor Family on 2026-11-21", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toBeVisible();
    await expect(page.locator(".calendar-prep-context")).toContainText("Integration review meeting");
  } finally { await request.delete(`/api/calendar/events/${event.id}`); }
});

test("teammate Inbox retains read and archive operations", async ({ page, request }, testInfo) => {
  await request.patch("/api/email/messages/EML-a3b4c5d6", { data: { folder: "inbox" } });
  await page.goto("/");
  await expect(page.locator(".topbar-title")).toHaveText("Inbox");
  await expect(page.locator(".email-simulation-note")).toContainText("Simulated Inbox");
  await page.locator(".email-item").filter({ hasText: "Down payment" }).click();
  await expect(page.locator(".email-detail-body")).toContainText("mid-December");
  await page.locator(".email-detail-actions").getByRole("button", { name: "Archive", exact: true }).click();
  await page.locator(".email-toolbar-left").getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.locator(".email-item").filter({ hasText: "Down payment" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("shared-inbox.png"), fullPage: true });
  await request.patch("/api/email/messages/EML-a3b4c5d6", { data: { folder: "inbox" } });
});


test("weekly navigation preserves every existing meeting and includes cross-month and weekend dates", async ({ page, request }, testInfo) => {
  const allMeetings = async () => (await Promise.all([10, 11, 12].map(async month =>
    (await request.get(`/api/calendar/events?year=2026&month=${month}`)).json()))).flat().sort((a, b) => a.id.localeCompare(b.id));
  const before = await allMeetings();
  const preparation = await state(request);
  await page.addInitScript(ids => localStorage.setItem("sia-seen-preparations", JSON.stringify(ids)), preparation.preparations.map(job => job.id));
  const monthRequests = new Set();
  let mutations = 0;
  page.on("request", req => {
    if (req.url().includes("/api/calendar/events")) {
      if (req.method() !== "GET") mutations++;
      monthRequests.add(new URL(req.url()).searchParams.get("month"));
    }
  });
  await openCalendar(page);
  await expect(page.locator(".cal-week-label")).toHaveText("Nov 9 – 15, 2026");
  await expect(page.getByRole("button", { name: /Show weekends|Hide weekends|View weekend meetings/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Saturday, November 14", exact: true }).click();
  await expect(page.locator(".cal-day-heading")).toHaveCount(7);
  await expect(page.getByRole("button", { name: "Edit event: Bond Duration Follow-Up: Thompson Trust, 2026-11-14 at 10:00", exact: true })).toBeVisible();
  for (let step = 0; step < 3; step++) await page.getByRole("button", { name: "Next week", exact: true }).click();
  await expect(page.locator(".cal-week-label")).toHaveText("Nov 30 – Dec 6, 2026");
  await expect.poll(() => monthRequests.has("11") && monthRequests.has("12")).toBe(true);
  await expect(page.getByRole("button", { name: "Edit event: Income Review: Patel, 2026-12-05 at 09:30", exact: true })).toBeVisible();
  for (let step = 0; step < 3; step++) await page.getByRole("button", { name: "Next week", exact: true }).click();
  await expect(page.locator(".cal-week-empty")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("empty-week.png"), fullPage: true });
  await page.getByRole("button", { name: "Next week", exact: true }).click();
  await expect(page.locator(".cal-week-label")).toHaveText("Dec 28, 2026 – Jan 3, 2027");
  await expect.poll(() => monthRequests.has("1")).toBe(true);
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await expect(page.locator(".cal-week-label")).toHaveText("Nov 9 – 15, 2026");
  expect(await allMeetings()).toEqual(before);
  expect(mutations).toBe(0);
});


test("a weekend demo day opens its actual meeting on mobile", async ({ page, request }) => {
  await page.setViewportSize({ width:390, height:900 });
  const preparation = await state(request);
  await page.route("**/api/meeting-preparations", route => route.fulfill({ json:{...preparation,now:"2026-11-14T08:00:00-05:00",preparations:[],enabled:false} }));
  await openCalendar(page);
  await expect(page.locator(".cal-week-label")).toHaveText("Nov 9 – 15, 2026");
  await expect(page.locator(".cal-day-heading")).toHaveCount(7);
  await expect(page.getByRole("button", { name:"Saturday, November 14", exact:true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name:"Edit event: Bond Duration Follow-Up: Thompson Trust, 2026-11-14 at 10:00", exact:true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

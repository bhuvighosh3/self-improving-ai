import { test, expect } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`manual preparation retains the meeting workspace and form at ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const queued = await (await request.post("/api/meeting-preparations/events/EVT-a3b4c5d6")).json();
    await expect.poll(async () => (await (await request.get("/api/meeting-preparations")).json()).preparations.find(job => job.id === queued.id)?.status).toBe("ready");
    let generations = 0;
    page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/api/briefings")) generations += 1; });
    await page.goto("/");
    if (width < 768) await page.getByLabel("Navigate to page").selectOption("meeting");
    else await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    const list = page.getByRole("complementary", { name: "Client meetings" });
    await expect(list).toBeVisible();
    await page.getByLabel("Search client meetings").fill("Okafor");
    await page.getByRole("button", { name: "Prepare another meeting", exact: true }).click();
    const panel = page.getByRole("region", { name: "Prepare another meeting", exact: true });
    await expect(panel).toBeVisible();
    await expect(page.getByRole("region", { name: "Meeting preparation workspace" })).toBeVisible();
    if (width >= 768) await expect(list).toBeVisible();
    else await expect(page.getByRole("button", { name: "All meetings", exact: true })).toBeVisible();
    await expect(panel.getByRole("article", { name: "Meeting briefing" })).toHaveCount(0);
    await panel.getByLabel("Client", { exact: true }).selectOption("CLI-005");
    await panel.getByLabel("Meeting focus", { exact: true }).fill("Confirm withdrawal planning and account details");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("manual-preparation.png"), fullPage: true });
    await panel.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(panel).toBeHidden();
    if (width < 768) await expect(list).toBeVisible();
    await expect(page.getByLabel("Search client meetings")).toHaveValue("Okafor");
    await page.getByRole("button", { name: "Open preparation for Okafor Family on 2026-11-20", exact: true }).click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toContainText("Okafor Family");
    if (width < 768) await page.getByRole("button", { name: "All meetings", exact: true }).click();
    await page.getByRole("button", { name: "Prepare another meeting", exact: true }).click();
    await expect(panel.getByLabel("Client", { exact: true })).toHaveValue("CLI-005");
    await expect(panel.getByLabel("Meeting focus", { exact: true })).toHaveValue("Confirm withdrawal planning and account details");
    expect(generations).toBe(0);
  });
}

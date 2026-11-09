import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Exercise browser workflows without consuming provider quota.
  await page.route("**/api/briefings", async route => {
    const payload = route.request().postDataJSON();
    await route.continue({ postData: JSON.stringify({ ...payload, mode: "simulation" }) });
  });
  await page.route("**/api/chat", async route => {
    const payload = route.request().postDataJSON();
    await route.continue({ postData: JSON.stringify(payload.meeting
      ? { ...payload, meeting: { ...payload.meeting, mode: "simulation" } } : payload) });
  });
});

test("meeting workflow exposes evidence coverage and persists local demo review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
  await page.getByRole("button", { name: "Prepare another meeting", exact: true }).click();
  await page.getByLabel("Client", { exact: true }).selectOption("CLI-004");
  await page.getByLabel("Meeting date", { exact: true }).fill("2026-10-30");
  await page.getByRole("button", { name: "Generate Meeting Brief", exact: true }).click();
  const process = page.locator("summary").filter({ hasText: "Preparation process" });
  await expect(process).toContainText("changed");
  await process.click();
  await expect(page.getByText("Deterministic demonstration; not model-reviewed.", { exact: false })).toBeVisible();
  await page.getByText("Recorded tools and evidence", { exact: true }).click();
  await expect(page.locator("pre")).toContainText("MINUTES-004");
  await page.getByRole("button", { name: "Check draft", exact: true }).click();
  await expect(process).toContainText("Check: pass");
  await page.getByRole("button", { name: "Mark as reviewed", exact: true }).click();
  await expect(page.locator(".meeting-toolbar")).toContainText("Reviewed");
  await page.getByRole("button", { name: "Edit draft", exact: true }).click();
  await page.getByLabel("Client Overview: item details").first().fill("Advisor updated draft.");
  await expect(page.locator(".meeting-toolbar")).toContainText("Needs review");
  await expect(process).toContainText("recheck required");
});

test("limited historical coverage retains routine review and focus edits invalidate the draft", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
  await page.getByRole("button", { name: "Prepare another meeting", exact: true }).click();
  await page.getByLabel("Client", { exact: true }).selectOption("CLI-002");
  await page.getByLabel("Meeting date", { exact: true }).fill("2026-10-30");
  await page.getByRole("button", { name: "Generate Meeting Brief", exact: true }).click();
  await expect(page.locator("summary").filter({ hasText: "Preparation process" })).toContainText("insufficient information");
  await expect(page.getByRole("heading", { name: "Routine meeting review" })).toBeVisible();
  await page.getByLabel("Meeting focus", { exact: true }).fill("Confirm current goals and open questions");
  await expect(page.getByText("Meeting inputs changed.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
});

test("Copilot asks only for the client before looking up the next appointment", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Copilot", exact: true }).click();
  await page.locator(".co-textarea").fill("Prepare my next meeting");
  await page.locator(".co-send").click();
  const form = page.locator(".co-meeting-form");
  await expect(form).toBeVisible();
  await expect(form.getByLabel("Meeting date")).toHaveCount(0);
  await expect(form.getByLabel("Meeting focus")).toHaveCount(0);
  await form.getByLabel("Client", { exact: true }).selectOption("CLI-002");
  await page.screenshot({ path: testInfo.outputPath("client-only-lookup.png"), fullPage: true });
  await form.getByRole("button", { name: "Find next meeting", exact: true }).click();
  await expect(page.getByRole("button", { name: "Open Meeting Brief", exact: true })).toBeVisible();
  await expect(form).toHaveCount(0);
  await expect(page.getByRole("log", { name: "Conversation" })).toContainText("Bond Duration Follow-Up: Thompson Trust");
});

for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
  test(`Copilot prepares from calendar without a form at ${viewport.width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const generations = [];
    page.on("request", request => {
      if (request.method() === "POST" && (request.url().endsWith("/api/briefings")
          || request.url().endsWith("/api/chat"))) {
        generations.push(request.url());
      }
    });
    await page.goto("/");
    if (viewport.width < 768) await page.getByLabel("Navigate to page").selectOption("copilot");
    else await page.getByRole("button", { name: "Copilot", exact: true }).click();
    await page.locator(".co-textarea").fill(
      "prepare a meeting prep for Thompson Trust");
    const completed = page.waitForResponse(response => response.url().endsWith("/api/chat") && response.request().method() === "POST");
    await page.locator(".co-send").click();
    const briefId = (await (await completed).json()).brief.id;
    const form = page.locator(".co-meeting-form");
    await expect(page.getByRole("button", { name: "Open Meeting Brief", exact: true })).toBeVisible();
    await expect(form).toHaveCount(0);
    await expect(page.getByRole("log", { name: "Conversation" })).toContainText("Bond Duration Follow-Up: Thompson Trust");
    await page.screenshot({ path: testInfo.outputPath("automatic-preparation.png"), fullPage: true });
    await page.getByRole("button", { name: "Open Meeting Brief", exact: true }).click();
    await expect(page.getByRole("region", { name: "Meeting preparation workspace" })).toBeVisible();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toHaveAttribute("data-brief-id", briefId);
    await expect(page.getByLabel("Meeting type")).toHaveCount(0);
    await expect(page.getByLabel("Meeting date", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Meeting at a glance" })).toContainText("Rate impact analysis on bond portfolio");
    await page.screenshot({ path: testInfo.outputPath("unified-meeting-prep.png"), fullPage: true });
    await expect(page.locator("summary").filter({ hasText: "Preparation process" })).toContainText("Check: pass");
    await page.getByRole("button", { name: "Check draft", exact: true }).click();
    await page.getByRole("button", { name: "Mark as reviewed", exact: true }).click();
    await expect(page.locator(".meeting-toolbar")).toContainText("Reviewed");
    if (viewport.width < 768) {
      await page.getByLabel("Navigate to page").selectOption("email");
      await page.getByLabel("Navigate to page").selectOption("meeting");
    } else {
      await page.getByRole("button", { name: "Inbox", exact: true }).first().click();
      await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
    }
    const row = page.getByRole("button", { name: "Open preparation for Thompson Trust on 2026-11-14", exact: true });
    await expect(row).toContainText("Reviewed");
    await row.click();
    await expect(page.getByRole("article", { name: "Meeting briefing" })).toHaveAttribute("data-brief-id", briefId);
    expect(generations).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

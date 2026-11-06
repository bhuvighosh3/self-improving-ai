import { test, expect } from "@playwright/test";

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

test("no significant changes retain routine review and agent mode is explicit", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
  await page.getByRole("button", { name: "Prepare another meeting", exact: true }).click();
  await page.getByLabel("Client", { exact: true }).selectOption("CLI-002");
  await page.getByLabel("Meeting date", { exact: true }).fill("2026-10-30");
  await page.getByRole("button", { name: "Generate Meeting Brief", exact: true }).click();
  await expect(page.locator("summary").filter({ hasText: "Preparation process" })).toContainText("unchanged");
  await expect(page.getByRole("heading", { name: "Routine meeting review" })).toBeVisible();
  await page.getByLabel("Generation mode").selectOption("agent");
  await expect(page.getByText("Meeting inputs changed.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
});

for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
  test(`Copilot hands off one retained brief at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const generations = [];
    page.on("request", request => {
      if (request.method() === "POST" && (request.url().endsWith("/api/briefings")
          || request.url().endsWith("/api/chat") && request.postDataJSON()?.meeting)) {
        generations.push(request.url());
      }
    });
    await page.goto("/");
    if (viewport.width < 768) await page.getByLabel("Navigate to page").selectOption("copilot");
    else await page.getByRole("button", { name: "Copilot", exact: true }).click();
    await page.locator(".co-textarea").fill(
      "Prepare a meeting for Okafor on 2026-11-11 at 2pm — Home purchase funding");
    await page.locator(".co-send").click();
    const form = page.locator(".co-meeting-form");
    await expect(form).toBeVisible();
    await expect(form.getByLabel("Client", { exact: true })).toHaveValue("CLI-004");
    await expect(form.getByLabel("Meeting date")).toHaveValue("2026-11-11");
    await expect(form.getByLabel("Generation mode")).toHaveValue("simulation");
    await form.getByLabel("Generation mode").selectOption("agent");
    await expect(form.getByLabel("Generation mode")).toHaveValue("agent");
    // The browser smoke test is explicitly offline; real acceptance is a separate command.
    await form.getByLabel("Generation mode").selectOption("simulation");
    await form.getByLabel("Meeting type").selectOption("goal_review");
    await form.getByRole("button", { name: "Generate Meeting Brief", exact: true }).click();
    await page.getByRole("button", { name: "Open Meeting Brief", exact: true }).click();
    await expect(page.getByLabel("Meeting type")).toHaveValue("goal_review");
    await expect(page.locator("summary").filter({ hasText: "Preparation process" })).toContainText("changed");
    await page.getByRole("button", { name: "Check draft", exact: true }).click();
    await page.getByRole("button", { name: "Mark as reviewed", exact: true }).click();
    await expect(page.locator(".meeting-toolbar")).toContainText("Reviewed");
    expect(generations).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

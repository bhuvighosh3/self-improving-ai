import { test, expect } from "@playwright/test";

test("meeting workflow exposes evidence coverage and persists local demo review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Meeting Prep", exact: true }).click();
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
  await page.getByLabel("Client", { exact: true }).selectOption("CLI-002");
  await page.getByLabel("Meeting date", { exact: true }).fill("2026-10-30");
  await page.getByRole("button", { name: "Generate Meeting Brief", exact: true }).click();
  await expect(page.locator("summary").filter({ hasText: "Preparation process" })).toContainText("unchanged");
  await expect(page.getByRole("heading", { name: "Routine meeting review" })).toBeVisible();
  await page.getByLabel("Generation mode").selectOption("agent");
  await expect(page.getByText("Meeting inputs changed.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark as reviewed", exact: true })).toBeDisabled();
});

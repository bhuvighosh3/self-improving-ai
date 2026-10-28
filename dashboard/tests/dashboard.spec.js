import { test, expect } from "@playwright/test";

test("copilot page loads by default with suggestions", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".co-empty h3")).toHaveText("How can I help?");
  const chips = page.locator(".co-chip");
  await expect(chips.first()).toBeVisible();
});

test("copilot confirms meeting details before generating a brief", async ({ page }) => {
  await page.goto("/");
  await page.fill(".co-textarea", "Get me ready for my 2pm with the Garcias");
  await page.click(".co-send");
  const bubble = page.locator(".bubble-ai");
  await expect(bubble.first()).toBeVisible({ timeout: 10000 });
  await expect(bubble.first()).toContainText("Garcia");
  await expect(bubble.first().getByLabel("Client", { exact: true })).toHaveValue("CLI-001");
  await expect(bubble.first().getByLabel("Time · New York")).toHaveValue("14:00");
  await expect(bubble.first().getByLabel("Meeting date")).toHaveValue("");
  await expect(page.locator(".trace-step")).toHaveCount(0);
});

test("copilot suggestion chip sends message", async ({ page }) => {
  await page.goto("/");
  await page.click(".co-chip >> nth=0");
  const bubble = page.locator(".bubble-ai");
  await expect(bubble.first()).toBeVisible({ timeout: 10000 });
});

test("copilot shows agent execution steps", async ({ page }) => {
  await page.goto("/");
  await page.fill(".co-textarea", "What's a sustainable monthly withdrawal for Priya Patel?");
  await page.click(".co-send");
  const steps = page.locator(".trace-step");
  await expect(steps.first()).toBeVisible({ timeout: 10000 });
  await expect(steps).toHaveCount(3);
});

test("dashboard page loads with kpi cards", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Overview")');
  const kpis = page.locator(".kpi");
  await expect(kpis).toHaveCount(4);
  await expect(kpis.first()).toContainText("Total AUM");
});

test("client page renders households", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Clients")');
  const cards = page.locator(".client-card");
  await expect(cards).toHaveCount(5);
  await expect(cards.first()).toContainText("Garcia");
});

test("client detail opens on click", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Clients")');
  await page.click(".client-card >> nth=0");
  await expect(page.locator(".detail-top")).toContainText("Garcia Family");
});

test("requests page renders all requests", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Requests")');
  const rows = page.locator("table tbody tr");
  await expect(rows).toHaveCount(10);
});

test("tools page renders tool catalog", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Tools")');
  const cards = page.locator(".tool-card");
  await expect(cards).toHaveCount(14);
});

test("news page renders articles", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("News")');
  const items = page.locator(".news-row");
  await expect(items).toHaveCount(12);
});

test("agents page shows three agents", async ({ page }) => {
  await page.goto("/");
  await page.click('button:has-text("Agents")');
  const cards = page.locator(".agent-card");
  await expect(cards).toHaveCount(3);
});

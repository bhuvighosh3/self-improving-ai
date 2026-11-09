import { test, expect } from "@playwright/test";

const QUESTIONS = [
  {
    id: "Q1",
    question: "When is my next meeting with Garcia?",
    expectTools: ["get_upcoming_events"],
    expectPattern: /garcia|meeting|schedule/i,
  },
  {
    id: "Q2",
    question: "Recent emails from Thompson family",
    expectTools: ["get_recent_emails"],
    expectPattern: /thompson|email/i,
  },
  {
    id: "Q3",
    question: "Garcia's risk tolerance and goals?",
    expectTools: ["get_client_info"],
    expectPattern: /risk|tolerance|goal/i,
  },
  {
    id: "Q4",
    question: "What is a Roth IRA?",
    expectTools: [],
    expectPattern: /roth|ira|retirement|tax/i,
  },
  {
    id: "Q5",
    question: "Garcia's current holdings",
    expectTools: ["get_client_holdings"],
    expectPattern: /hold|position|portfolio|share/i,
  },
  {
    id: "Q6",
    question: "Latest CRM notes for Thompson",
    expectTools: ["get_crm_summary"],
    expectPattern: /thompson|note|crm|meeting|review/i,
  },
  {
    id: "Q7",
    question: "Show me Garcia's holdings and upcoming meetings",
    expectTools: ["get_client_holdings", "get_upcoming_events"],
    expectPattern: /garcia/i,
  },
  {
    id: "Q8",
    question: "Prepare meeting brief for Garcia",
    expectTools: [],
    expectPattern: /garcia|brief|meeting|prep/i,
  },
  {
    id: "Q9",
    question: "Risk profile of Garcia's portfolio",
    expectTools: [],
    expectPattern: /risk|portfolio|garcia|return/i,
  },
  {
    id: "Q10",
    question: "Explain tax-loss harvesting",
    expectTools: [],
    expectPattern: /tax.loss|harvest|offset|capital/i,
  },
];

async function sendAndWait(page, question, pattern, timeout = 300_000) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const copilotBtn = page.locator('button:has-text("Copilot")');
  if (await copilotBtn.isVisible()) await copilotBtn.click();
  const textarea = page.locator(".co-textarea");
  await textarea.waitFor({ state: "visible", timeout: 10_000 });
  await textarea.fill(question);
  await textarea.press("Enter");
  const aiResponse = page.locator(".bubble-ai .bubble-text").last();
  await aiResponse.waitFor({ state: "visible", timeout });
  await expect(page.locator(".dots")).toHaveCount(0, { timeout });
  const responseText = await aiResponse.textContent();
  expect(responseText.length).toBeGreaterThan(10);
  expect(responseText).toMatch(pattern);
  await expect(page.locator(".bubble-err")).toHaveCount(0);
}

test.describe.configure({ mode: "serial" });

for (const q of QUESTIONS) {
  if (q.id === "Q8") continue;
  test(`${q.id}: ${q.question}`, async ({ page }) => {
    test.setTimeout(300_000);
    await sendAndWait(page, q.question, q.expectPattern);
  });
}

test("Q8: Prepare meeting brief for Garcia", async ({ page }) => {
  test.setTimeout(600_000);

  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const copilotBtn = page.locator('button:has-text("Copilot")');
  if (await copilotBtn.isVisible()) await copilotBtn.click();
  const textarea = page.locator(".co-textarea");
  await textarea.waitFor({ state: "visible", timeout: 10_000 });
  await textarea.fill("Prepare meeting brief for Garcia");
  await textarea.press("Enter");

  // Wait for the first AI response (may be text or a meeting form)
  await page.locator(".bubble-ai").first().waitFor({ state: "visible", timeout: 300_000 });
  await expect(page.locator(".dots")).toHaveCount(0, { timeout: 300_000 });

  // Handle whichever form state appears
  const meetingForm = page.locator(".co-meeting-form");
  if (await meetingForm.isVisible({ timeout: 3_000 }).catch(() => false)) {
    // multiple_meetings: click the first meeting choice
    const choiceBtn = page.locator(".co-meeting-choices .meeting-btn").first();
    if (await choiceBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await choiceBtn.click();
    } else {
      // Full form or client_required: submit the pre-filled form
      const submitBtn = meetingForm.locator(".meeting-btn.primary");
      await submitBtn.click();
    }

    // Wait for the brief response after form submission
    await expect(page.locator(".dots")).toHaveCount(0, { timeout: 600_000 });
  }

  // Verify we got a meaningful response about Garcia
  const lastResponse = page.locator(".bubble-ai .bubble-text").last();
  await lastResponse.waitFor({ state: "visible", timeout: 600_000 });
  const text = await lastResponse.textContent();
  expect(text).toMatch(/garcia|brief|meeting|prep/i);
  await expect(page.locator(".bubble-err")).toHaveCount(0);
});

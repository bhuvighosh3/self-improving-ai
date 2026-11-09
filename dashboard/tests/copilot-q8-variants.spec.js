import { test, expect } from "@playwright/test";

const Q8_VARIANTS = [
  "Prepare meeting brief for Garcia",
  "Get me ready for my 2pm with the Garcias",
  "Meeting briefing for Garcia",
  "prep Garcia",
  "I need a brief for my next meeting with Garcia",
];

test.describe.configure({ mode: "serial" });

for (const question of Q8_VARIANTS) {
  test(`Q8 variant: ${question}`, async ({ page }) => {
    test.setTimeout(600_000);

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const copilotBtn = page.locator('button:has-text("Copilot")');
    if (await copilotBtn.isVisible()) await copilotBtn.click();
    const textarea = page.locator(".co-textarea");
    await textarea.waitFor({ state: "visible", timeout: 10_000 });
    await textarea.fill(question);
    await textarea.press("Enter");

    // Wait for first AI response
    await page.locator(".bubble-ai").first().waitFor({ state: "visible", timeout: 300_000 });
    await expect(page.locator(".dots")).toHaveCount(0, { timeout: 300_000 });

    // Handle meeting form if it appears
    const meetingForm = page.locator(".co-meeting-form");
    const formVisible = await meetingForm.isVisible().catch(() => false);

    if (formVisible) {
      // multiple_meetings: click the first choice
      const choiceBtn = page.locator(".co-meeting-choices .meeting-btn").first();
      const choiceVisible = await choiceBtn.isVisible().catch(() => false);

      if (choiceVisible) {
        await choiceBtn.click();
      } else {
        // Full form or client_required: submit pre-filled form
        const submitBtn = meetingForm.locator(".meeting-btn.primary");
        await submitBtn.click();
      }

      await expect(page.locator(".dots")).toHaveCount(0, { timeout: 600_000 });
    }

    // Verify response
    const lastResponse = page.locator(".bubble-ai .bubble-text").last();
    await lastResponse.waitFor({ state: "visible", timeout: 600_000 });
    const text = await lastResponse.textContent();
    expect(text).toMatch(/garcia|brief|meeting|prep/i);
    await expect(page.locator(".bubble-err")).toHaveCount(0);
  });
}

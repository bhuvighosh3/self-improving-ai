import { test, expect } from "@playwright/test";

test("portfolio calculations use actual tool results and show draft assumptions", async ({page})=>{
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.getByRole("heading",{name:"Current value: $146,750.00"})).toBeVisible();
  await expect(page.locator(".portfolio-results")).toContainText("19.8637");
  await expect(page.locator(".portfolio-results")).toContainText("unapproved draft inputs");
  await page.screenshot({path:"../artifacts/screenshots/portfolio-desktop.png",fullPage:true});
  await page.getByLabel("Analysis",{exact:true}).selectOption("risk");
  await expect(page.locator(".portfolio-results")).toHaveCount(0);
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.locator(".portfolio-results")).toContainText("5.295%");
});

test("Patel projection includes withdrawals", async ({page})=>{
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByLabel("Client",{exact:true}).selectOption("CLI-005");
  await page.getByLabel("Analysis",{exact:true}).selectOption("projection");
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.locator(".portfolio-results")).toContainText("Annual withdrawal $50,400.00");
  await expect(page.locator(".portfolio-results")).toContainText("Ending median: $0.00");
});

test("mobile portfolio form fits viewport", async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await page.getByLabel("Navigate to page").selectOption("portfolio");
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.locator(".portfolio-results table")).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({path:"../artifacts/screenshots/portfolio-mobile.png",fullPage:true});
});

test("explicit target reaches the backend and resets on client change",async({page})=>{
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByLabel("Client",{exact:true}).selectOption("CLI-002");
  await page.getByLabel("Stock target (%)").fill("60");
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.locator(".portfolio-results")).toContainText("$54,820.00");
  await page.getByLabel("Client",{exact:true}).selectOption("CLI-001");
  await expect(page.getByLabel("Stock target (%)")).toHaveValue("");
  await expect(page.locator(".portfolio-results")).toHaveCount(0);
});

test("projection exposes actual goal, horizon conflict and sampling uncertainty",async({page})=>{
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByLabel("Client",{exact:true}).selectOption("CLI-003");
  await page.getByLabel("Analysis",{exact:true}).selectOption("projection");
  await page.getByLabel("Years",{exact:true}).fill("10");
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.locator(".portfolio-results")).toContainText("Goal: $2,000,000.00 in 10 years");
  await expect(page.locator(".portfolio-results")).toContainText("25-year general horizon");
  await expect(page.locator(".portfolio-results")).toContainText("95% sampling interval");
  await expect(page.locator(".portfolio-results")).toContainText("Inputs changed for this run: years");
  await page.screenshot({path:"../artifacts/screenshots/portfolio-projection.png",fullPage:true});
});

test("a stalled analysis can be cancelled and late results cannot replace a new result",async({page})=>{
  let release;
  let started;
  const waiting=new Promise(resolve=>{started=resolve;});
  await page.route("**/api/portfolio/execute",async route=>{
    started();
    await new Promise(resolve=>{release=resolve;});
    await route.fulfill({json:{status:"success",mode:"explicit_tool_execution",result:{source:"late-old-result"},trace:[]}}).catch(()=>{});
  });
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await waiting;
  await page.getByRole("button",{name:"Cancel analysis",exact:true}).click();
  await expect(page.getByRole("button",{name:"Connections",exact:true})).toBeEnabled();
  await expect(page.getByLabel("Analysis",{exact:true})).toBeEnabled();
  await page.unroute("**/api/portfolio/execute");
  await page.getByLabel("Analysis",{exact:true}).selectOption("risk");
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await expect(page.locator(".portfolio-results")).toContainText("5.295%");
  release();
  await expect(page.locator(".portfolio-results")).not.toContainText("late-old-result");
});

test("a stalled model analysis has a deadline and editable controls recover",async({page})=>{
  await page.clock.install();
  await page.route("**/api/portfolio/agent",()=>{});
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByLabel("Workflow").selectOption("agent");
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await expect(page.getByRole("button",{name:"Cancel analysis",exact:true})).toBeVisible();
  await page.clock.fastForward(126000);
  await expect(page.getByRole("alert")).toContainText("Analysis timed out");
  await expect(page.getByRole("button",{name:"Run analysis",exact:true})).toBeEnabled();
  await expect(page.getByLabel("Your question")).toBeEnabled();
});

test("unreadable analysis responses restore controls and allow retry",async({page})=>{
  await page.route("**/api/portfolio/execute",route=>route.fulfill({status:502,contentType:"text/html",body:"upstream unavailable"}));
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("unreadable response");
  await expect(page.getByRole("button",{name:"Run analysis",exact:true})).toBeEnabled();
  await page.unroute("**/api/portfolio/execute");
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await expect(page.locator(".portfolio-results")).toContainText("19.8637");
});

import { test, expect } from "@playwright/test";

async function mockConnections(page,{agentConfigured=false,marketConfigured=false}={}) {
  const control={
    state:{market:{provider:"twelve_data",configured:marketConfigured},
      agent:{provider:"gemini",configured:agentConfigured,model:"gemini-3.5-flash-lite",model_options:[
        {id:"gemini-3.5-flash-lite",label:"Gemini 3.5 Flash-Lite",description:"Recommended for this prototype.",recommended:true},
        {id:"gemini-3.1-flash-lite",label:"Gemini 3.1 Flash-Lite",description:"Lightweight alternative."},
        {id:"gemini-3.6-flash",label:"Gemini 3.6 Flash",description:"General agent tasks."},
        {id:"gemini-3.8-flash",label:"Gemini 3.8 Flash",description:"Newer Flash option."}
      ]}},
    probes:[],saves:[],failLoads:false,failSaves:false,onProbe:null,
    keys:{market:marketConfigured?"saved-market-key":"",agent:agentConfigured?"saved-gemini-key":""}
  };
  await page.route("**/api/portfolio/connections**",async route=>{
    const path=new URL(route.request().url()).pathname;
    const method=route.request().method();
    const tab=path.includes("/agent")?"agent":"market";
    if(path.endsWith("/test")) {
      const payload=route.request().postDataJSON() || {};
      control.probes.push({tab,...payload,effectiveKey:payload.api_key||control.keys[tab]});
      if(control.onProbe&&await control.onProbe(route,payload,tab)) return;
      await route.fulfill({json:tab==="market"
        ?{status:"success",symbol:"AAPL",price:123.45,currency:"USD",as_of:"2026-10-30"}
        :{status:"success",source:"gemini",model:payload.model||control.state.agent.model,
          message:"Gemini accepted a generation request."}});
      return;
    }
    if(method==="GET"&&control.failLoads) {
      await route.fulfill({status:503,json:{detail:"Could not load settings. Try again."}});return;
    }
    if(method==="PUT") {
      const payload=route.request().postDataJSON();
      control.saves.push({tab,...payload});
      if(control.failSaves) {
        await route.fulfill({status:500,json:{detail:"Could not save this connection."}});return;
      }
      if(payload.api_key) control.keys[tab]=payload.api_key;
      control.state[tab].configured=Boolean(control.keys[tab]);
      if(tab==="agent")control.state.agent.model=payload.model;
    }
    if(method==="DELETE") {control.keys[tab]="";control.state[tab].configured=false;}
    await route.fulfill({json:control.state});
  });
  return control;
}
async function openConnections(page,{mobile=false,agent=false}={}) {
  await page.goto("/");
  if(mobile)await page.getByLabel("Navigate to page").selectOption("portfolio");
  else await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByRole("button",{name:"Connections",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"Connections"});
  if(agent)await dialog.getByRole("tab",{name:"Portfolio Agent",exact:true}).click();
  await dialog.getByLabel(agent?"Gemini API key":"Market data API key",{exact:true}).waitFor();
  return dialog;
}

test("market settings save, test and remove without retaining the saved key in the input",async({page})=>{
  const control=await mockConnections(page);
  const dialog=await openConnections(page);
  await expect(dialog.getByLabel("Market data provider")).toHaveValue("twelve_data");
  const key=dialog.getByLabel("Market data API key",{exact:true});
  await expect(key).toHaveAttribute("type","password");
  await key.fill("fake-browser-market-key");
  await dialog.getByRole("button",{name:"Save connection",exact:true}).click();
  await expect(dialog).toContainText("New analyses use this connection immediately");
  await expect(key).toHaveValue("");
  expect(control.probes).toHaveLength(0);
  await dialog.getByRole("button",{name:"Test with AAPL",exact:true}).click();
  await expect(dialog).toContainText("AAPL quote received");
  expect(control.probes[0].api_key).toBeNull();
  expect(control.probes[0].effectiveKey).toBe("fake-browser-market-key");
  expect(await page.evaluate(()=>JSON.stringify({...localStorage}))).not.toContain("fake-browser");
  await dialog.getByRole("button",{name:"Remove API key",exact:true}).click();
  await expect(dialog).toContainText("Saved key removed");
  await dialog.getByRole("button",{name:"Test with AAPL",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Enter a market-data API key");
  expect(control.probes).toHaveLength(1);
  await dialog.getByRole("button",{name:"Done",exact:true}).click();
  await expect(dialog).toHaveCount(0);
});

test("Gemini models reuse both an entered key and a saved key on mobile",async({page})=>{
  const control=await mockConnections(page);
  await page.setViewportSize({width:390,height:844});
  let dialog=await openConnections(page,{mobile:true,agent:true});
  const models=dialog.getByRole("combobox",{name:"Gemini model",exact:true});
  const key=dialog.getByLabel("Gemini API key",{exact:true});
  await expect(models.locator("option")).toHaveCount(4);
  await expect(models).not.toContainText("Gemini 4");
  await models.selectOption("gemini-3.1-flash-lite");
  await key.fill("fake-browser-gemini-key");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog).toContainText("Gemini connection verified");
  await expect(key).toHaveValue("fake-browser-gemini-key");
  expect(control.saves).toHaveLength(0);

  await models.selectOption("gemini-3.6-flash");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog).toContainText("Gemini connection verified");
  expect(control.probes.slice(0,2).map(item=>item.effectiveKey)).toEqual([
    "fake-browser-gemini-key","fake-browser-gemini-key"]);
  expect(control.probes[1].model).toBe("gemini-3.6-flash");
  expect(control.state.agent.model).toBe("gemini-3.5-flash-lite");

  await dialog.getByRole("button",{name:"Save connection",exact:true}).click();
  await expect(dialog).toContainText("New analyses use this connection immediately");
  await expect(key).toHaveValue("");
  await models.selectOption("gemini-3.8-flash");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog).toContainText("Gemini connection verified");
  expect(control.probes[2].api_key).toBeNull();
  expect(control.probes[2].effectiveKey).toBe("fake-browser-gemini-key");
  expect(control.probes[2].model).toBe("gemini-3.8-flash");
  expect(control.state.agent.model).toBe("gemini-3.6-flash");

  await dialog.getByRole("tab",{name:"Market data",exact:true}).click();
  await dialog.getByLabel("Market data API key",{exact:true}).fill("unsaved-market-key");
  await dialog.getByRole("tab",{name:"Portfolio Agent",exact:true}).click();
  await expect(key).toHaveValue("");
  await dialog.getByRole("tab",{name:"Market data",exact:true}).click();
  await expect(dialog.getByLabel("Market data API key",{exact:true})).toHaveValue("unsaved-market-key");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button",{name:"Connections",exact:true}).click();
  dialog=page.getByRole("dialog",{name:"Connections"});
  await expect(dialog.getByLabel("Market data API key",{exact:true})).toHaveValue("");
});

test("no API key shows an immediate prompt with no test request and no modal lock",async({page})=>{
  const control=await mockConnections(page);
  const dialog=await openConnections(page);
  await dialog.getByRole("button",{name:"Test with AAPL",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Enter a market-data API key");
  await expect(dialog.getByLabel("Market data API key",{exact:true})).toBeFocused();
  await dialog.getByRole("tab",{name:"Portfolio Agent",exact:true}).click();
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Enter a Gemini API key");
  await expect(dialog.getByLabel("Gemini API key",{exact:true})).toBeFocused();
  expect(control.probes).toHaveLength(0);
  await expect(dialog.getByRole("button",{name:"Close connections",exact:true})).toBeEnabled();
  await dialog.getByRole("button",{name:"Close connections",exact:true}).click();
  await expect(dialog).toHaveCount(0);
});

test("waiting tests can be cancelled and the dialog can close while a request is pending",async({page})=>{
  const control=await mockConnections(page,{agentConfigured:true});
  const held=[];
  control.onProbe=async route=>{held.push(route);return true;};
  let dialog=await openConnections(page,{agent:true});
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog.getByRole("button",{name:"Cancel test",exact:true})).toBeVisible();
  await expect(dialog.getByRole("button",{name:"Close connections",exact:true})).toBeEnabled();
  await dialog.getByRole("button",{name:"Cancel test",exact:true}).click();
  await expect(dialog).toContainText("Test cancelled");
  await expect(dialog.getByLabel("Gemini model",{exact:true})).toBeEnabled();
  await dialog.getByLabel("Gemini model",{exact:true}).selectOption("gemini-3.1-flash-lite");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog.getByRole("button",{name:"Cancel test",exact:true})).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  for(const route of held)await route.abort().catch(()=>{});
  await page.getByRole("button",{name:"Connections",exact:true}).click();
  dialog=page.getByRole("dialog",{name:"Connections"});
  await dialog.getByRole("tab",{name:"Portfolio Agent",exact:true}).click();
  await expect(dialog.getByLabel("Gemini model",{exact:true})).toHaveValue("gemini-3.5-flash-lite");
  await expect(dialog.getByRole("button",{name:"Test Gemini",exact:true})).toBeEnabled();
});

test("a stalled test times out and restores editable controls",async({page})=>{
  const control=await mockConnections(page,{agentConfigured:true});
  let held;
  control.onProbe=async route=>{held=route;return true;};
  const dialog=await openConnections(page,{agent:true});
  await page.clock.install();
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect.poll(()=>control.probes.length).toBe(1);
  await page.clock.fastForward(16000);
  await expect(dialog.getByRole("alert")).toContainText("timed out");
  await expect(dialog.getByRole("button",{name:"Test Gemini",exact:true})).toBeEnabled();
  await expect(dialog.getByLabel("Gemini model",{exact:true})).toBeEnabled();
  await expect(dialog.getByRole("button",{name:"Cancel test",exact:true})).toHaveCount(0);
  await dialog.getByRole("button",{name:"Done",exact:true}).click();
  if(held)await held.abort().catch(()=>{});
});

test("settings load failures can be reloaded without trapping the dialog",async({page})=>{
  const control=await mockConnections(page);
  control.failLoads=true;
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByRole("button",{name:"Connections",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"Connections"});
  await expect(dialog.getByRole("alert")).toContainText("Could not load settings");
  await expect(dialog.getByRole("button",{name:"Close connections",exact:true})).toBeEnabled();
  control.failLoads=false;
  await dialog.getByRole("button",{name:"Reload settings",exact:true}).click();
  await expect(dialog.getByLabel("Market data API key",{exact:true})).toBeVisible();
  await expect(dialog.getByRole("alert")).toHaveCount(0);
});

test("failed saves keep the draft key so it can still be tested",async({page})=>{
  const control=await mockConnections(page);
  control.failSaves=true;
  const dialog=await openConnections(page,{agent:true});
  const key=dialog.getByLabel("Gemini API key",{exact:true});
  await key.fill("retry-with-this-key");
  await dialog.getByRole("button",{name:"Save connection",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Could not save");
  await expect(key).toHaveValue("retry-with-this-key");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog).toContainText("Gemini connection verified");
  expect(control.probes[0].api_key).toBe("retry-with-this-key");
});

test("failed model tests keep the key and permit testing another model immediately",async({page})=>{
  const control=await mockConnections(page);
  control.onProbe=async route=>{
    if(control.probes.length!==1)return false;
    await route.fulfill({json:{status:"error",error:{code:"MODEL_BUSY",message:"Model temporarily busy (503)."}}});
    return true;
  };
  const dialog=await openConnections(page,{agent:true});
  const key=dialog.getByLabel("Gemini API key",{exact:true});
  await key.fill("same-draft-key");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("temporarily busy");
  await dialog.getByLabel("Gemini model",{exact:true}).selectOption("gemini-3.1-flash-lite");
  await dialog.getByRole("button",{name:"Test Gemini",exact:true}).click();
  await expect(dialog).toContainText("Gemini connection verified");
  expect(control.probes.map(item=>item.effectiveKey)).toEqual(["same-draft-key","same-draft-key"]);
});

test("a busy analysis shows the provider reason and recovery actions",async({page})=>{
  await page.route("**/api/portfolio/agent",route=>route.fulfill({json:{
    run_id:"busy-test",mode:"adk_gemini",status:"error",model:"gemini-example",
    result:{status:"error",source:"gemini",error:{code:"MODEL_BUSY",retryable:true,
      message:"The selected Gemini model is temporarily busy (503). Try again shortly or choose another model in Connections."}},trace:[]
  }}));
  await page.goto("/");
  await page.getByRole("button",{name:"Portfolio Analysis",exact:true}).click();
  await page.getByLabel("Workflow").selectOption("agent");
  await page.getByRole("button",{name:"Run analysis",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("temporarily busy (503)");
  await expect(page.getByRole("button",{name:"Retry analysis",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Open connection settings",exact:true})).toBeVisible();
  await expect(page.locator(".portfolio-results")).toContainText("Execution stopped · gemini-example");
  await expect(page.locator(".portfolio-results")).toContainText("Source: gemini");
});


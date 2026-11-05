import React, { useEffect, useRef, useState } from "react";
import ConnectionSettings from "./ConnectionSettings";
import { requestJson } from "./connectionRequest";
import "./portfolio.css";

const money = (n,currency="USD") => new Intl.NumberFormat("en-US", {style:"currency",currency,maximumFractionDigits:2}).format(n);
const percent = n => `${(n*100).toFixed(3)}%`;

export default function PortfolioPanel({clients}) {
  const [client, setClient] = useState("CLI-001");
  const [task, setTask] = useState("allocation");
  const [symbol, setSymbol] = useState("AAPL");
  const [start, setStart] = useState("2026-09-01");
  const [end, setEnd] = useState("2026-09-30");
  const [mode, setMode] = useState("calculate");
  const [message, setMessage] = useState("Show the Garcia Family CLI-001 allocation drift against its draft 60/40 target.");
  const [run, setRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(null);
  useEffect(()=>()=>{pending.current?.abort();pending.current=null;},[]);
  const [overrides, setOverrides] = useState({});
  const [connectionsOpen, setConnectionsOpen] = useState(false);
  const changeScenario = (key, value) => {setOverrides({...overrides,[key]:value}); setRun(null); setError("");};
  const changeContext = setter => value => {reset(setter)(value); setOverrides({});};
  const reset = fn => value => {fn(value); setRun(null); setError("");setNotice("");};
  function cancelAnalysis() {
    const controller=pending.current;
    pending.current=null;
    controller?.abort();
    setBusy(false);setError("");setNotice("Stopped waiting. You can change the inputs and run again. A provider request already sent may still use quota.");
  }
  async function submit(event) {
    event.preventDefault();
    if(pending.current) return;
    const controller=new AbortController();
    pending.current=controller;
    setBusy(true); setError("");setNotice(""); setRun(null);
    try {
      const scenario = Object.fromEntries(Object.entries(overrides).filter(([,value])=>value !== "").map(([key,value])=>[key,Number(value)]));
      if (scenario.target_stock_weight !== undefined) scenario.target_stock_weight /= 100;
      const data = await requestJson(`/api/portfolio/${mode === "agent" ? "agent" : "execute"}`, {
        method:"POST",signal:controller.signal,timeoutMs:mode==="agent"?125000:15000,
        timeoutMessage:"Analysis timed out. You can retry or choose another model in Connections.",
        body: JSON.stringify(mode === "agent" ? {message} : {task, client_id:client, symbol, start_date:start, end_date:end,...scenario})
      });
      if(pending.current!==controller) return;
      if(!["success","error"].includes(data?.status)) throw new Error("The service returned an incomplete analysis. Try again.");
      setRun(data);
      if (data.status === "error") setError(data.result?.error?.message || "This request is unavailable.");
    } catch (exception) {if(pending.current===controller&&exception.kind!=="cancelled")setError(exception.message || "Could not reach the service.");}
    finally {if(pending.current===controller){pending.current=null;setBusy(false);}}
  }
  const result = run?.result;
  return <section className="portfolio-panel">
    <div className="portfolio-heading"><h2>Portfolio Analysis</h2><button type="button" className="portfolio-connections-button" disabled={busy} onClick={()=>setConnectionsOpen(true)}>Connections</button></div>
    <p>Synthetic households · Draft assumptions · Hypothetical adjustments only</p>
    {connectionsOpen&&<ConnectionSettings onClose={()=>setConnectionsOpen(false)} onChanged={()=>{setRun(null);setError("");}}/>}
    <form onSubmit={submit} className="portfolio-form">
      <label>Workflow<select aria-label="Workflow" value={mode} disabled={busy} onChange={e=>reset(setMode)(e.target.value)}>
        <option value="calculate">Portfolio calculations</option><option value="agent">Ask Portfolio Agent (Gemini)</option>
      </select></label>
      {mode === "agent" ? <label className="portfolio-wide">Your question<textarea aria-label="Your question" value={message} required maxLength={3000} disabled={busy} onChange={e=>reset(setMessage)(e.target.value)}/></label> : <>
        <label>Client<select aria-label="Client" value={client} disabled={busy} onChange={e=>changeContext(setClient)(e.target.value)}>{clients.map(c=><option key={c.client_id} value={c.client_id}>{c.profile.name}</option>)}</select></label>
        <label>Analysis<select aria-label="Analysis" value={task} disabled={busy} onChange={e=>changeContext(setTask)(e.target.value)}>
          <option value="allocation">Allocation drift</option><option value="risk">Risk and return</option>
          <option value="projection">Goal projection</option><option value="holdings">Holdings</option>
          <option value="quote">External quote</option><option value="history">External history</option>
        </select></label>
        {["quote","history"].includes(task) && <label>Symbol<input aria-label="Symbol" value={symbol} required disabled={busy} onChange={e=>reset(setSymbol)(e.target.value)}/></label>}
        {task === "history" && <><label>Start date<input aria-label="Start date" type="date" value={start} required disabled={busy} onChange={e=>reset(setStart)(e.target.value)}/></label><label>End date<input aria-label="End date" type="date" value={end} required disabled={busy} onChange={e=>reset(setEnd)(e.target.value)}/></label></>}
        {task === "allocation" && <label>Stock target (%)<input aria-label="Stock target (%)" type="number" min="0" max="100" step="any" placeholder="Use stored draft" value={overrides.target_stock_weight ?? ""} disabled={busy} onChange={e=>changeScenario("target_stock_weight",e.target.value)}/></label>}
        {task === "projection" && <>{[["target_amount","Goal amount (USD)",1],["years","Years",1],["annual_contribution","Annual contribution (USD)",0],["annual_withdrawal","Annual withdrawal (USD)",0]].map(([key,label,min])=><label key={key}>{label}<input aria-label={label} type="number" min={min} max={key === "years" ? 120 : undefined} step={key === "years" ? 1 : "any"} placeholder="Use stored draft" value={overrides[key] ?? ""} disabled={busy} onChange={e=>changeScenario(key,e.target.value)}/></label>)}<p className="portfolio-wide">Leave fields blank to use the stored draft. Entering zero explicitly replaces a stored cash flow.</p></>}
      </>}
      <button className="btn-primary" disabled={busy}>{busy ? "Running…" : "Run analysis"}</button>
      {busy&&<button type="button" onClick={cancelAnalysis}>Cancel analysis</button>}
    </form>
    {busy&&<p role="status">{mode==="agent"?"Asking Gemini and checking portfolio tools… This can take up to two minutes.":"Running the selected calculation…"} You can cancel waiting.</p>}
    {notice&&<p role="status">{notice}</p>}
    {mode === "agent" && <p>Uses the configured Gemini account. Missing configuration is reported explicitly.</p>}
    {error && <div className="portfolio-error" role="alert">{error}{(["MISSING_API_KEY","MISSING_MODEL_CONFIGURATION"].includes(run?.result?.error?.code)||run?.result?.source==="gemini")&&<button type="button" className="portfolio-configure-link" onClick={()=>setConnectionsOpen(true)}>Open connection settings</button>}{run?.result?.error?.retryable&&<button type="button" className="portfolio-configure-link" disabled={busy} onClick={submit}>Retry analysis</button>}</div>}
    {run && <div className="portfolio-results" aria-live="polite">
      <p>{run.status==="error"?"Execution stopped":run.mode === "explicit_tool_execution" ? "Calculated directly with portfolio tools" : "Portfolio Agent response"}{run.model?` · ${run.model}`:""}</p>
      {result?.asset_classes && <><h3>Current value: {money(result.total_market_value)}</h3><div className="portfolio-table"><table><thead><tr><th>Asset class</th><th>Current</th><th>Target</th><th>Drift (pp)</th><th>Hypothetical adjustment</th></tr></thead><tbody>{Object.entries(result.asset_classes).map(([key,value])=><tr key={key}><td>{key}</td><td>{percent(value.current_weight)}</td><td>{percent(value.target_weight)}</td><td>{value.drift_percentage_points.toFixed(4)}</td><td>{money(value.hypothetical_adjustment_usd)}</td></tr>)}</tbody></table></div></>}
      {result?.annual_volatility !== undefined && <><h3>Annual expected return: {percent(result.annual_expected_return)}</h3><p>Annual volatility: {percent(result.annual_volatility)} · Draft stock/bond model</p></>}
      {result?.success_probability !== undefined && <><h3>Simulated goal success: {(result.success_probability*100).toFixed(1)}%</h3><p>Goal: {money(result.goal.target_amount)} in {result.goal.years} years · Starting value: {money(result.initial_value)}</p><p>95% sampling interval: {percent(result.success_probability_interval.lower)}–{percent(result.success_probability_interval.upper)} · {result.num_simulations.toLocaleString()} paths · Seed {result.seed}. This interval excludes uncertainty in the model and assumptions.</p><p>Ending median: {money(result.ending_value_median)} · 10th–90th percentile: {money(result.ending_value_p10)}–{money(result.ending_value_p90)}</p><p>Depletion probability: {percent(result.depletion_probability)} · {result.goal.years} years · Annual contribution {money(result.goal.annual_contribution)} · Annual withdrawal {money(result.goal.annual_withdrawal)}</p><p>End-year cash flows; nominal USD. Includes all fixture accounts without modeling access restrictions.</p><p className="portfolio-warning">Stored draft note: {result.stored_goal.assumption}</p><p>Inputs changed for this run: {Object.keys(result.scenario_overrides).join(", ") || "None; stored draft used"}.</p></>}
      {result?.accounts && <><h3>Total fixture value: {money(result.total_market_value)}</h3>{result.accounts.map(a=><div key={a.account_id}><h4>{a.account_id}</h4><ul>{a.holdings.map((h,i)=><li key={i}>{h.ticker}: {money(h.market_value)}</li>)}</ul></div>)}</>}
      {result?.price && <h3>{result.symbol}: {money(result.price,result.currency)} · {result.currency} · {result.as_of}</h3>}
      {result?.prices && <><h3>{result.symbol}: {result.count} daily closes</h3><p>{result.data_start} to {result.data_end} · {result.currency} · {result.price_type}</p></>}
      {result?.source && <p>Source: {result.source}{result.assumptions_version ? ` · Assumptions: ${result.assumptions_version}` : ""}</p>}
      {result?.warnings?.map((text,i)=><p className="portfolio-warning" key={i}>{text}</p>)}
      {run.response && <p className="portfolio-answer">{run.response}</p>}
      <details><summary>Execution evidence</summary><pre>{JSON.stringify({run_id:run.run_id,status:run.status,metadata:run.metadata,trace:run.trace},null,2)}</pre></details>
    </div>}
  </section>;
}

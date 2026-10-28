import React, { useEffect, useState } from "react";
import MeetingPrep from "./MeetingPrep";

const COLORS = ["#3563e9","#7c3aed","#16a34a","#ca8a04","#dc2626","#db2777","#0284c7","#ea580c"];
const TICKER_C = {VTSAX:"#3563e9",VTIAX:"#7c3aed",BND:"#16a34a",AAPL:"#dc2626",QQQ:"#ca8a04",ARKK:"#db2777",TSLA:"#0284c7",MUB:"#ea580c",VYM:"#6d28d9",VTIP:"#0d9488"};
const RISK_CHIP = {conservative:"chip-green",moderate:"chip-accent",aggressive:"chip-red"};
const INTENT_CHIP = {portfolio_projection:"chip-accent",meeting_briefing:"chip-violet",tax_estimation:"chip-amber",risk_analysis:"chip-green",income_planning:"chip-accent",compliance_check:"chip-red",general:"chip-teal"};
const SECTOR_CHIP = {macro:"chip-accent",tech:"chip-violet",fixed_income:"chip-green",real_estate:"chip-amber",international:"chip-accent",tax:"chip-amber",equities:"chip-green",regulatory:"chip-red",auto:"chip-violet",lifestyle:"chip-red",entertainment:"chip-red",health:"chip-green"};
const AGENT_DOT = {request_orchestrator:"#3563e9",portfolio_estimation_agent:"#16a34a",meeting_briefing_agent:"#7c3aed"};

function fmt$(n){return n>=1e6?`$${(n/1e6).toFixed(1)}M`:n>=1e3?`$${(n/1e3).toFixed(0)}K`:`$${n}`}
function pct(v,t){return t?((v/t)*100).toFixed(1):0}

function Ic({d,s=16}){return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{__html:d}}/>}

const ic={
  copilot:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  dash:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  people:'<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  inbox:'<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  wrench:'<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  news:'<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><line x1="10" y1="6" x2="18" y2="6"/><line x1="10" y1="10" x2="18" y2="10"/><line x1="10" y1="14" x2="14" y2="14"/>',
  bot:'<rect x="4" y="4" width="16" height="16" rx="2"/><circle cx="9" cy="10" r="1.5"/><circle cx="15" cy="10" r="1.5"/><path d="M9 15h6"/>',
  back:'<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  send:'<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
};

const PAGE_TITLE={copilot:"Copilot",meeting:"Meeting Prep",dashboard:"Overview",clients:"Clients",requests:"Requests",tools:"Tools",news:"News",agents:"Agents"};

/* ════ Copilot ════ */
function Copilot({clients}){
  const [input,setInput]=useState("");
  const [cid,setCid]=useState("");
  const [msgs,setMsgs]=useState([]);
  const [busy,setBusy]=useState(false);

  const hints=[
    "Get me ready for my 2pm with the Garcias",
    "How much tax if we sold all AAPL for the Garcias?",
    "Sustainable monthly withdrawal for Priya Patel?",
    "Meeting briefing for Wei Chen — ARKK tax-loss harvesting",
    "Is the Garcia portfolio properly diversified?",
    "Quick summary of the Thompson Trust",
  ];

  async function send(txt){
    const t=txt||input;
    if(!t.trim())return;
    setInput("");
    setMsgs(p=>[...p,{role:"user",text:t,time:ts()}]);
    setBusy(true);
    try{
      const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:t,client_id:cid||null})});
      const d=await r.json();
      setMsgs(p=>[...p,{role:"ai",text:d.response,intent:d.intent,agents:d.agents_used,steps:d.steps,client_id:d.client_id,mode:d.mode,time:ts()}]);
    }catch{
      setMsgs(p=>[...p,{role:"err",text:"Could not reach the server.",time:ts()}]);
    }
    setBusy(false);
  }

  function onKey(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}

  return(
    <div className="copilot">
      <div className="copilot-scroll">
        <div className="copilot-inner">
          {msgs.length===0&&(
            <div className="co-empty">
              <div className="co-empty-icon"><Ic d={ic.copilot} s={24}/></div>
              <h3>How can I help?</h3>
              <p>Ask about any client — portfolio projections, meeting prep, tax analysis, risk reviews. I'll route your request through the right agents.</p>
              <div className="co-chips">
                {hints.map((h,i)=><button key={i} className="co-chip" onClick={()=>send(h)}>{h}</button>)}
              </div>
            </div>
          )}

          {msgs.map((m,i)=>(
            <div key={i} className={`msg msg-${m.role}`}>
              {m.role==="user"&&<div className="bubble bubble-user"><div className="bubble-text">{m.text}</div><div className="bubble-time">{m.time}</div></div>}
              {m.role==="ai"&&(
                <div className="bubble bubble-ai">
                  {m.steps?.length>0&&(
                    <div className="trace">
                      {m.steps.map((s,j)=>(
                        <div key={j} className="trace-step">
                          <div className="trace-dot" style={{background:AGENT_DOT[s.agent]||"#666"}}/>
                          <div>
                            <span className="trace-agent">{humanAgent(s.agent)}</span>{" "}
                            <span className="trace-detail">{s.detail}</span>
                            {s.tools_called?.length>0&&<div className="trace-tools">{s.tools_called.map(t=><span key={t} className="chip chip-accent">{t}</span>)}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="bubble-text" dangerouslySetInnerHTML={{__html:md(m.text)}}/>
                  <div className="bubble-foot">
                    {m.intent&&<span className={`chip ${INTENT_CHIP[m.intent]||"chip-accent"}`}>{m.intent.replace(/_/g," ")}</span>}
                    {m.mode==="simulation"&&<span className="chip chip-amber">demo</span>}
                    <span className="bubble-time" style={{marginTop:0}}>{m.time}</span>
                  </div>
                </div>
              )}
              {m.role==="err"&&<div className="bubble bubble-err">{m.text}</div>}
            </div>
          ))}

          {busy&&<div className="msg msg-ai"><div className="bubble bubble-ai"><div className="dots"><div className="dot"/><div className="dot"/><div className="dot"/></div></div></div>}
        </div>
      </div>

      <div className="co-input-area">
        <div className="co-input-inner">
          <select className="co-select" value={cid} onChange={e=>setCid(e.target.value)}>
            <option value="">Auto-detect client</option>
            {(clients||[]).map(c=><option key={c.client_id} value={c.client_id}>{c.profile?.name}</option>)}
          </select>
          <div className="co-row">
            <textarea className="co-textarea" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={onKey} placeholder="Ask about a client..." rows={1} disabled={busy}/>
            <button className="co-send" onClick={()=>send()} disabled={!input.trim()||busy}><Ic d={ic.send} s={16}/></button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ════ Dashboard ════ */
function Dashboard({stats,clients,requests,news}){
  const allH={};
  (clients||[]).forEach(c=>c.accounts?.forEach(a=>a.holdings?.forEach(h=>{allH[h.ticker]=(allH[h.ticker]||0)+h.market_value})));
  const tot=Object.values(allH).reduce((s,v)=>s+v,0)||1;
  const sorted=Object.entries(allH).sort((a,b)=>b[1]-a[1]);

  return(<>
    <div className="kpi-row">
      <div className="kpi"><div className="kpi-label">Total AUM</div><div className="kpi-num c-accent">{fmt$(stats?.total_aum||0)}</div><div className="kpi-hint">{stats?.total_accounts||0} accounts</div></div>
      <div className="kpi"><div className="kpi-label">Clients</div><div className="kpi-num c-green">{stats?.total_clients||0}</div><div className="kpi-hint">active households</div></div>
      <div className="kpi"><div className="kpi-label">Requests</div><div className="kpi-num c-amber">{stats?.total_requests||0}</div><div className="kpi-hint">{Object.keys(stats?.intent_breakdown||{}).length} intent types</div></div>
      <div className="kpi"><div className="kpi-label">Tools</div><div className="kpi-num c-violet">{stats?.total_tools||0}</div><div className="kpi-hint">across 3 agents</div></div>
    </div>

    <div className="row-2">
      <div className="card">
        <div className="card-head"><span>Portfolio Allocation</span></div>
        <div className="card-body">
          <div className="alloc-bar">
            {sorted.map(([t,v])=><div key={t} className="alloc-seg" style={{flex:v/tot,background:TICKER_C[t]||"#666"}}>{v/tot>0.06?t:""}</div>)}
          </div>
          <div className="alloc-legend">
            {sorted.map(([t,v])=><div key={t} className="alloc-legend-item"><div className="alloc-swatch" style={{background:TICKER_C[t]||"#666"}}/>{t} {pct(v,tot)}%</div>)}
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-head"><span>Intent Breakdown</span></div>
        <div className="card-body">
          {Object.entries(stats?.intent_breakdown||{}).map(([k,v])=>(
            <div key={k} style={{marginBottom:10}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
                <span style={{fontSize:12.5}}>{k.replace(/_/g," ")}</span>
                <span style={{fontSize:12.5,color:"var(--text-4)"}}>{v}</span>
              </div>
              <div className="bar-track"><div className="bar-fill" style={{width:`${(v/(stats?.total_requests||1))*100}%`,background:"var(--accent)"}}/></div>
            </div>
          ))}
        </div>
      </div>
    </div>

    <div className="row-2" style={{marginTop:12}}>
      <div className="card">
        <div className="card-head"><span>Recent Requests</span></div>
        <div className="card-body flush">
          <table><thead><tr><th>ID</th><th>Request</th><th>Intent</th></tr></thead>
          <tbody>{(requests||[]).slice(0,5).map(r=>(
            <tr key={r.id}><td className="mono">{r.id}</td><td style={{maxWidth:260,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.request_text}</td><td><span className={`chip ${INTENT_CHIP[r.intent]||"chip-accent"}`}>{r.intent?.replace(/_/g," ")}</span></td></tr>
          ))}</tbody></table>
        </div>
      </div>
      <div className="card">
        <div className="card-head"><span>Latest News</span></div>
        <div className="card-body">
          {(news||[]).filter(n=>!["lifestyle","entertainment","health"].includes(n.sector)).slice(0,4).map(n=>(
            <div key={n.id} style={{marginBottom:10,paddingBottom:10,borderBottom:"1px solid var(--border-subtle)"}}>
              <div style={{fontSize:13,fontWeight:600}}>{n.headline}</div>
              <div style={{display:"flex",gap:6,marginTop:3}}><span style={{fontSize:11,color:"var(--text-4)"}}>{n.date}</span><span className={`chip ${SECTOR_CHIP[n.sector]||"chip-accent"}`}>{n.sector}</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  </>);
}

/* ════ Clients ════ */
function Clients({clients,onSelect}){
  return(
    <div className="client-grid">
      {(clients||[]).map((c,i)=>{
        const aum=c.accounts?.reduce((s,a)=>s+a.holdings?.reduce((s2,h)=>s2+h.market_value,0),0)||0;
        const ini=c.profile?.name?.split(" ").map(w=>w[0]).join("").slice(0,2);
        return(
          <div key={c.client_id} className="client-card" onClick={()=>onSelect(c)}>
            <div className="cc-top">
              <div className="cc-avatar" style={{background:COLORS[i%COLORS.length]}}>{ini}</div>
              <div><div className="cc-name">{c.profile?.name}</div><div className="cc-sub">{c.profile?.primary_contact}</div></div>
            </div>
            <div className="cc-stats">
              <div><div className="cc-stat-label">AUM</div><div className="cc-stat-val">{fmt$(aum)}</div></div>
              <div><div className="cc-stat-label">Risk</div><div className="cc-stat-val"><span className={`chip ${RISK_CHIP[c.profile?.risk_tolerance]||""}`}>{c.profile?.risk_tolerance}</span></div></div>
              <div><div className="cc-stat-label">Accounts</div><div className="cc-stat-val">{c.accounts?.length||0}</div></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ════ Client Detail ════ */
function ClientDetail({client,onBack,onPrepare}){
  const p=client.profile||{};
  const allH={};
  client.accounts?.forEach(a=>a.holdings?.forEach(h=>{allH[h.ticker]=(allH[h.ticker]||0)+h.market_value}));
  const tot=Object.values(allH).reduce((s,v)=>s+v,0)||1;
  const sorted=Object.entries(allH).sort((a,b)=>b[1]-a[1]);

  return(
    <div className="detail">
      <div className="detail-top">
        <div>
          <button className="detail-back" onClick={onBack}><Ic d={ic.back} s={14}/> Clients</button>
          <div className="detail-name">{p.name}</div>
          <div className="detail-id">{client.client_id} &middot; {p.primary_contact}</div>
        </div>
        <div className="meeting-actions"><span className={`chip ${RISK_CHIP[p.risk_tolerance]||""}`} style={{fontSize:12,padding:"5px 12px"}}>{p.risk_tolerance} risk</span><button className="meeting-btn primary" onClick={()=>onPrepare(client)}>Generate Meeting Brief</button></div>
      </div>

      <div className="detail-grid">
        <div><div className="dg-label">Annual Income</div><div className="dg-val">{fmt$(p.annual_income||0)}</div></div>
        <div><div className="dg-label">Tax Bracket</div><div className="dg-val">{p.tax_bracket||"N/A"}</div></div>
        <div><div className="dg-label">Horizon</div><div className="dg-val">{p.investment_horizon||"N/A"}</div></div>
        <div><div className="dg-label">State</div><div className="dg-val">{p.state||"N/A"}</div></div>
        <div><div className="dg-label">Goals</div><div className="dg-val">{p.goals?.map(g=>g.replace(/_/g," ")).join(", ")||"N/A"}</div></div>
        {p.notes&&<div><div className="dg-label">Notes</div><div className="dg-val">{p.notes}</div></div>}
      </div>

      <div className="card">
        <div className="card-head"><span>Allocation</span><span style={{fontSize:12,color:"var(--text-3)"}}>{fmt$(tot)}</span></div>
        <div className="card-body">
          <div className="alloc-bar">{sorted.map(([t,v])=><div key={t} className="alloc-seg" style={{flex:v/tot,background:TICKER_C[t]||"#666"}}>{v/tot>0.08?t:""}</div>)}</div>
          <div className="alloc-legend">{sorted.map(([t,v])=><div key={t} className="alloc-legend-item"><div className="alloc-swatch" style={{background:TICKER_C[t]||"#666"}}/>{t} {fmt$(v)} ({pct(v,tot)}%)</div>)}</div>
        </div>
      </div>

      <div className="row-2" style={{marginTop:12}}>
        <div className="card">
          <div className="card-head"><span>Holdings</span></div>
          <div className="card-body flush">
            {client.accounts?.map(acct=>(
              <div key={acct.account_id}>
                <div className="acct-header"><span>{acct.account_id}</span><span className="chip chip-accent">{acct.type?.replace(/_/g," ")}</span></div>
                <table><thead><tr><th>Ticker</th><th>Shares</th><th>Value</th><th>Basis</th><th>P/L</th></tr></thead>
                <tbody>{acct.holdings?.map(h=>{const gl=h.market_value-h.cost_basis;return(
                  <tr key={h.ticker}><td style={{fontWeight:600}}>{h.ticker}</td><td>{h.shares}</td><td>{fmt$(h.market_value)}</td><td className="mono">{fmt$(h.cost_basis)}</td><td className={gl>=0?"gain":"loss"}>{gl>=0?"+":""}{fmt$(gl)}</td></tr>
                )})}</tbody></table>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><span>CRM Notes</span></div>
          <div className="card-body">
            <div className="note-list">
              {(client.crm_notes||[]).map((n,i)=>(
                <div key={i} className="note-item">
                  <div className="note-head"><span className="note-date">{n.date}</span><span className="note-author">{n.author}</span></div>
                  <div className="note-body">{n.text}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ════ Requests ════ */
function Requests({requests}){
  return(
    <div className="card">
      <div className="card-head"><span>Advisor Requests</span><span className="chip chip-accent">{requests?.length||0}</span></div>
      <div className="card-body flush">
        <table><thead><tr><th>ID</th><th>Request</th><th>Client</th><th>Intent</th><th>Routed To</th></tr></thead>
        <tbody>{(requests||[]).map(r=>(
          <tr key={r.id}>
            <td className="mono">{r.id}</td>
            <td>{r.request_text}</td>
            <td className="mono">{r.client_id}</td>
            <td><span className={`chip ${INTENT_CHIP[r.intent]||"chip-accent"}`}>{r.intent?.replace(/_/g," ")}</span></td>
            <td>{r.expected_agents?.map(a=><span key={a} className="chip chip-violet" style={{marginRight:3}}>{humanAgent(a)}</span>)}</td>
          </tr>
        ))}</tbody></table>
      </div>
    </div>
  );
}

/* ════ Tools ════ */
function Tools({tools}){
  return(
    <div className="tool-grid">
      {(tools||[]).map(t=>(
        <div key={t.name} className="tool-card">
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
            <div className="tool-name">{t.name}</div>
            <span className="chip chip-violet" style={{fontSize:10}}>{humanAgent(t.agent)}</span>
          </div>
          <div className="tool-desc">{t.description}</div>
          <div className="tool-params">({t.parameters?.join(", ")||"none"})</div>
          {t.caveat&&<div className="tool-warn">{t.caveat}</div>}
        </div>
      ))}
    </div>
  );
}

/* ════ News ════ */
function News({news}){
  return(
    <div className="news-list">
      {(news||[]).map(n=>(
        <div key={n.id} className="news-row">
          <div className="news-date">{n.date}</div>
          <div className="news-main">
            <div className="news-hl">{n.headline}</div>
            <div className="news-txt">{n.text}</div>
            <div className="news-foot"><span className={`chip ${SECTOR_CHIP[n.sector]||"chip-accent"}`}>{n.sector}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ════ Agents ════ */
function Agents({stats}){
  const agents=stats?.agents||[];
  return(<>
    <div className="agent-grid">
      {agents.map(a=>(
        <div key={a.id} className="agent-card">
          <div className="agent-head"><div><div className="agent-name">{a.name}</div><div className="agent-id">{a.id}</div></div><span className="chip chip-green">{a.status}</span></div>
          <div className="agent-chips"><span className="chip chip-accent">{a.model}</span><span className="chip chip-violet">{a.tools} tools</span></div>
        </div>
      ))}
    </div>

    <div className="card" style={{marginTop:14}}>
      <div className="card-head"><span>Request Routing</span></div>
      <div className="card-body">
        {Object.entries(stats?.agent_usage||{}).map(([a,c])=>(
          <div key={a} style={{marginBottom:10}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
              <span style={{fontSize:12.5}}>{humanAgent(a)}</span>
              <span style={{fontSize:12.5,color:"var(--text-4)"}}>{c} requests</span>
            </div>
            <div className="bar-track"><div className="bar-fill" style={{width:`${(c/(stats?.total_requests||1))*100}%`,background:"var(--violet)"}}/></div>
          </div>
        ))}
      </div>
    </div>

    <div className="card" style={{marginTop:14}}>
      <div className="card-head"><span>Architecture</span></div>
      <div className="card-body">
        <div className="arch">
          <div className="arch-box" style={{background:"var(--accent-soft)",border:"1.5px solid var(--accent)"}}>Orchestrator<small>Intent parsing &middot; Agent routing</small></div>
          <div style={{display:"flex",gap:40}}><div className="arch-line"/><div className="arch-line"/></div>
          <div className="arch-row">
            <div className="arch-box" style={{background:"var(--green-soft)",border:"1.5px solid var(--green)"}}>Portfolio Agent<small>Holdings &middot; Projections &middot; Tax</small></div>
            <div className="arch-box" style={{background:"var(--violet-soft)",border:"1.5px solid var(--violet)"}}>Briefing Agent<small>CRM &middot; News &middot; Compliance</small></div>
          </div>
        </div>
      </div>
    </div>
  </>);
}

/* ════ Helpers ════ */
function humanAgent(id){return({request_orchestrator:"Orchestrator",portfolio_estimation_agent:"Portfolio",meeting_briefing_agent:"Briefing"})[id]||id.replace(/_/g," ")}
function ts(){return new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}
function md(t){
  if(!t)return"";
  return t
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,"<em>$1</em>")
    .replace(/^- (.+)$/gm,"<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>)/,"<ul>$1</ul>")
    .replace(/\n\n/g,"<br/><br/>")
    .replace(/\n/g,"<br/>");
}

/* ════ App ════ */
export default function App(){
  const [page,setPage]=useState("copilot");
  const [health,setHealth]=useState(null);
  const [stats,setStats]=useState(null);
  const [clients,setClients]=useState([]);
  const [requests,setRequests]=useState([]);
  const [tools,setTools]=useState([]);
  const [news,setNews]=useState([]);
  const [selClient,setSelClient]=useState(null);
  const [meetingClient,setMeetingClient]=useState(null);

  useEffect(()=>{
    const f=(u,s)=>fetch(u).then(r=>r.json()).then(s).catch(()=>{});
    f("/api/health",setHealth);
    f("/api/stats",setStats);
    f("/api/clients",setClients);
    f("/api/requests",setRequests);
    f("/api/tools",setTools);
    f("/api/news",setNews);
  },[]);

  const nav=(p)=>{setPage(p);setSelClient(null);setMeetingClient(null)};
  const prepareMeeting=(client)=>{setMeetingClient(client);setPage("meeting");setSelClient(null)};

  const menu=[
    {id:"copilot",ic:ic.copilot,label:"Copilot"},
    {id:"meeting",ic:ic.inbox,label:"Meeting Prep"},
    {id:"dashboard",ic:ic.dash,label:"Overview"},
    {id:"clients",ic:ic.people,label:"Clients"},
    {id:"requests",ic:ic.inbox,label:"Requests"},
    {id:"tools",ic:ic.wrench,label:"Tools"},
    {id:"news",ic:ic.news,label:"News"},
    {id:"agents",ic:ic.bot,label:"Agents"},
  ];

  return(
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>Self-Improving AI</h1>
          <div className="brand-sub">Wealth Management</div>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-group-label">Main</div>
          {menu.slice(0,3).map(m=><button key={m.id} className={`nav-btn ${page===m.id?"active":""}`} onClick={()=>nav(m.id)}><Ic d={m.ic}/>{m.label}</button>)}
          <div className="nav-group-label">Data</div>
          {menu.slice(3,7).map(m=><button key={m.id} className={`nav-btn ${page===m.id?"active":""}`} onClick={()=>nav(m.id)}><Ic d={m.ic}/>{m.label}</button>)}
          <div className="nav-group-label">System</div>
          {menu.slice(7).map(m=><button key={m.id} className={`nav-btn ${page===m.id?"active":""}`} onClick={()=>nav(m.id)}><Ic d={m.ic}/>{m.label}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className={`pulse-dot ${health?.status==="ok"?"":"off"}`}/>
          {health?.status==="ok"?"Online":"Offline"}
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div className="topbar-title">{PAGE_TITLE[page]}</div>
          <select className="mobile-page-select" aria-label="Navigate to page" value={page} onChange={event=>nav(event.target.value)}>{menu.map(item=><option value={item.id} key={item.id}>{item.label}</option>)}</select>
        </div>
        <div className={page==="copilot"?"page-flush":"page"}>
          {page==="copilot"&&<Copilot clients={clients}/>}
          {page==="meeting"&&<MeetingPrep clients={clients} selectedClient={meetingClient}/>}
          {page==="dashboard"&&<Dashboard stats={stats} clients={clients} requests={requests} news={news}/>}
          {page==="clients"&&!selClient&&<Clients clients={clients} onSelect={setSelClient}/>}
          {page==="clients"&&selClient&&<ClientDetail client={selClient} onBack={()=>setSelClient(null)} onPrepare={prepareMeeting}/>}
          {page==="requests"&&<Requests requests={requests}/>}
          {page==="tools"&&<Tools tools={tools}/>}
          {page==="news"&&<News news={news}/>}
          {page==="agents"&&<Agents stats={stats}/>}
        </div>
      </div>
    </div>
  );
}

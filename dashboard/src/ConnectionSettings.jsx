import React, { useEffect, useRef, useState } from "react";
import { connectionRequest, CONNECTION_TEST_TIMEOUT_MS } from "./connectionRequest";

export default function ConnectionSettings({onClose,onChanged}) {
  const dialog=useRef(null);
  const keyInput=useRef(null);
  const active=useRef(true);
  const pending=useRef(null);
  const sequence=useRef(0);
  const [tab,setTab]=useState("market");
  const [status,setStatus]=useState(null);
  const [draftKeys,setDraftKeys]=useState({market:"",agent:""});
  const [model,setModel]=useState("");
  const [visible,setVisible]=useState(false);
  const [action,setAction]=useState(null);
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");
  const [test,setTest]=useState(null);
  const key=draftKeys[tab];
  const configured=Boolean(status?.[tab]?.configured);
  const modelOptions=status?.agent?.model_options || [];
  const selectedModel=modelOptions.find(option=>option.id===model);
  const busy=action!==null;

  function begin(name) {
    pending.current?.controller.abort();
    const operation={id:++sequence.current,controller:new AbortController()};
    pending.current=operation;
    setAction(name);setError("");setNotice("");setTest(null);
    return operation;
  }
  const current=operation=>active.current&&pending.current?.id===operation.id;
  function finish(operation) {
    if(current(operation)){pending.current=null;setAction(null);}
  }
  function showError(operation,exception) {
    if(current(operation)&&exception.kind!=="cancelled") setError(exception.message);
  }
  function cancelTest() {
    const operation=pending.current;
    pending.current=null;
    operation?.controller.abort();
    setAction(null);setTest(null);setError("");setNotice("Test cancelled. You can change the model or try again.");
  }
  function close() {
    pending.current?.controller.abort();
    pending.current=null;
    setDraftKeys({market:"",agent:""});setVisible(false);
    onClose();
  }
  async function loadSettings() {
    const operation=begin("load");
    try {
      const data=await connectionRequest("",{signal:operation.controller.signal});
      if(!data.market||!data.agent||!Array.isArray(data.agent.model_options))
        throw new Error("Could not load connection settings. Try loading them again.");
      if(current(operation)){setStatus(data);setModel(value=>value||data.agent.model);}
    } catch(exception){showError(operation,exception);}
    finally {finish(operation);}
  }
  useEffect(()=>{
    active.current=true;
    if(!dialog.current.open) dialog.current.showModal();
    loadSettings();
    return ()=>{
      active.current=false;
      pending.current?.controller.abort();
      pending.current=null;
    };
  },[]);

  function changeTab(value) {
    setTab(value);setVisible(false);setNotice("");setError("");setTest(null);
  }
  function validate() {
    if(!key.trim()&&!configured) {
      setError(tab==="agent"?"Enter a Gemini API key before testing or saving.":"Enter a market-data API key before testing or saving.");
      setNotice("");setTest(null);keyInput.current?.focus();
      return false;
    }
    if(tab==="agent"&&!selectedModel) {
      setError("Choose a Gemini model from the list.");
      return false;
    }
    return true;
  }
  function payload() {
    return tab==="market" ? {provider:"twelve_data",api_key:key.trim()||null}
      : {model,api_key:key.trim()||null};
  }
  async function save(event) {
    event.preventDefault();
    if(pending.current||busy||!validate()) return;
    const selectedTab=tab;
    const body=JSON.stringify(payload());
    const operation=begin("save");
    try {
      const data=await connectionRequest(`/${selectedTab}`,{
        method:"PUT",body,signal:operation.controller.signal
      });
      if(current(operation)){
        setStatus(data);setDraftKeys(value=>({...value,[selectedTab]:""}));setVisible(false);
        setNotice("Saved. New analyses use this connection immediately.");onChanged();
      }
    }catch(exception){showError(operation,exception);}
    finally{finish(operation);}
  }
  async function remove() {
    if(pending.current||busy) return;
    const selectedTab=tab;
    const operation=begin("remove");
    try {
      const data=await connectionRequest(`/${selectedTab}`,{
        method:"DELETE",signal:operation.controller.signal
      });
      if(current(operation)){
        setStatus(data);setDraftKeys(value=>({...value,[selectedTab]:""}));setVisible(false);
        setNotice("Saved key removed. Enter a key to test or save this connection again.");onChanged();
      }
    }catch(exception){showError(operation,exception);}
    finally{finish(operation);}
  }
  async function testConnection() {
    if(pending.current||busy||!validate()) return;
    const selectedTab=tab;
    const body=JSON.stringify(payload());
    const operation=begin("test");
    try {
      const result=await connectionRequest(`/${selectedTab}/test`,{
        method:"POST",body,signal:operation.controller.signal,
        timeoutMs:CONNECTION_TEST_TIMEOUT_MS
      });
      if(!current(operation)) return;
      if(result.status!=="success") {
        if(["MISSING_API_KEY","MISSING_MODEL_CONFIGURATION"].includes(result.error?.code))
          setStatus(value=>({...value,[selectedTab]:{...value[selectedTab],configured:false}}));
        throw new Error(result.error?.message || "The provider did not accept this test.");
      }
      setTest(result);
    }catch(exception){showError(operation,exception);}
    finally{finish(operation);}
  }

  return <dialog ref={dialog} className="connection-dialog" aria-labelledby="connection-title"
    onCancel={event=>{event.preventDefault();close();}}
    onClick={event=>{if(event.target===event.currentTarget)close();}}>
    <div className="connection-content">
      <div className="connection-heading">
        <div><h2 id="connection-title">Connections</h2><p>Configure the services used by Portfolio Analysis.</p></div>
        <button type="button" className="connection-close" aria-label="Close connections" onClick={close}>×</button>
      </div>
      <div className="connection-tabs" role="tablist" aria-label="Connection type"
        onKeyDown={event=>{
          if(!busy&&["ArrowLeft","ArrowRight","Home","End"].includes(event.key)){
            event.preventDefault();
            const target=event.key==="Home"?"market":event.key==="End"?"agent":tab==="market"?"agent":"market";
            changeTab(target);event.currentTarget.querySelector(`#connection-tab-${target}`).focus();
          }
        }}>
        <button id="connection-tab-market" type="button" role="tab" tabIndex={tab==="market"?0:-1}
          aria-selected={tab==="market"} aria-controls="connection-panel" disabled={busy}
          onClick={()=>changeTab("market")}>Market data</button>
        <button id="connection-tab-agent" type="button" role="tab" tabIndex={tab==="agent"?0:-1}
          aria-selected={tab==="agent"} aria-controls="connection-panel" disabled={busy}
          onClick={()=>changeTab("agent")}>Portfolio Agent</button>
      </div>
      <div id="connection-panel" role="tabpanel" aria-labelledby={`connection-tab-${tab}`}>
        {action==="load" ? <p role="status">Loading connections…</p> : status ? <form onSubmit={save} noValidate>
          <fieldset disabled={busy}>
            <label>{tab==="market"?"Market data provider":"Model provider"}
              <select aria-label={tab==="market"?"Market data provider":"Model provider"}
                value={tab==="market"?"twelve_data":"gemini"} onChange={()=>{}}>
                {tab==="market"?<option value="twelve_data">Twelve Data</option>:<option value="gemini">Google Gemini</option>}
              </select>
            </label>
            <p className="connection-description">{tab==="market"
              ?"Twelve Data supplies external quotes and historical prices."
              :"One Gemini API key is shared by all models below. Changing the model does not require a new key."}</p>
            <p className={`connection-state ${configured?"is-configured":""}`}>
              {key.trim()?"New key entered · Not saved":configured?"Using saved API key":"Not configured"}
            </p>
            {tab==="agent"&&<>
              <label>Gemini model
                <select aria-label="Gemini model" value={model} onChange={event=>{
                  setModel(event.target.value);setNotice("");setError("");setTest(null);
                }}>
                  {!selectedModel&&<option value={model} disabled>{model?`Current: ${model} — choose an option`:"Select a model"}</option>}
                  {modelOptions.map(option=><option key={option.id} value={option.id}>
                    {option.label}{option.recommended?" — Recommended":""} · Free tier available
                  </option>)}
                </select>
              </label>
              {selectedModel&&<p className="connection-description">{selectedModel.description}</p>}
              <p className="connection-description">Free-tier availability and quota depend on your Google project. <a href="https://ai.google.dev/gemini-api/docs/rate-limits" target="_blank" rel="noreferrer">Check project limits</a></p>
            </>}
            <label htmlFor="connection-api-key">{tab==="market"?"Market data API key":"Gemini API key"}</label>
            <div className="connection-key-row">
              <input ref={keyInput} id="connection-api-key" aria-label={tab==="market"?"Market data API key":"Gemini API key"}
                type={visible?"text":"password"} value={key} maxLength={4096} autoComplete="off"
                autoCapitalize="none" spellCheck={false}
                placeholder={configured?"Using saved key; paste only to replace it":"Paste your API key"}
                onChange={event=>{
                  const value=event.target.value;
                  setDraftKeys(keys=>({...keys,[tab]:value}));setNotice("");setError("");setTest(null);
                }}/>
              <button type="button" aria-pressed={visible} onClick={()=>setVisible(!visible)}>{visible?"Hide":"Show"}</button>
            </div>
            <p className="connection-description">{configured
              ?"A blank field uses the saved key. Keys entered here stay available while you switch models or tabs."
              :"You can test a key before saving it. It stays in this window while you try other models."}</p>
            <div className="connection-actions">
              <button type="submit" className="connection-primary">{action==="save"?"Saving…":"Save connection"}</button>
              <button type="button" onClick={testConnection}>{tab==="market"?"Test with AAPL":"Test Gemini"}</button>
              {configured&&<button type="button" className="connection-remove" onClick={remove}>Remove API key</button>}
            </div>
            <p className="connection-description">Test checks the current form without saving it. Save applies these settings to Portfolio Analysis.</p>
          </fieldset>
        </form> : null}
        {action==="test"&&<p role="status">Testing {tab==="agent"?"the selected Gemini model":"AAPL quote"}… Up to 15 seconds. You can cancel.</p>}
        {notice&&<p className="connection-notice" role="status">{notice}</p>}
        {error&&<p className="portfolio-error" role="alert">{error}</p>}
        {!status&&action!=="load"&&<button type="button" onClick={loadSettings}>Reload settings</button>}
        {test&&<div className="connection-test-result" role="status">
          {tab==="market"?<><strong>AAPL quote received</strong><p>{test.price} {test.currency} · {test.as_of}</p>
            <p>Latest available quote; real-time status remains unverified.</p></>
            :<><strong>Gemini connection verified</strong><p>{test.model}</p><p>{test.message}</p></>}
          <p>Test completed. Use Save connection to apply any changes.</p>
        </div>}
      </div>
      <div className="connection-footer">
        {action==="test"&&<button type="button" onClick={cancelTest}>Cancel test</button>}
        <button type="button" onClick={close}>Done</button>
      </div>
    </div>
  </dialog>;
}


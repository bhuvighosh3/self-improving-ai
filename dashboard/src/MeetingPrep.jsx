import React, { useEffect, useRef, useState } from "react";
import "./meeting-prep.css";
import { loadMeetingDraft, saveMeetingDraft } from "./meetingDraftStore";
import { CalendarSymbol, meetingLabel } from "./calendarFormat";

export default function MeetingPrep({ incomingBrief, calendarEvent, onBackToCalendar }) {
  const [saved] = useState(() => loadMeetingDraft(incomingBrief?.id) || (incomingBrief ? { brief: incomingBrief } : null));
  const [brief, setBrief] = useState(saved?.brief || null);
  const [reviewedAt, setReviewedAt] = useState(saved?.reviewedAt || null);
  const [revision, setRevision] = useState(saved?.revision || 1);
  const [edited, setEdited] = useState(saved?.edited || false);
  const [quality, setQuality] = useState(() => {
    if (saved?.checkFailed) return null;
    if (saved && "quality" in saved) return saved.quality;
    return saved?.edited ? null : saved?.brief.workflow?.quality || null;
  });
  const [checkFailed, setCheckFailed] = useState(Boolean(saved?.checkFailed));
  const [serverRevision, setServerRevision] = useState(saved?.serverRevision || 1);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedSource, setSelectedSource] = useState(null);
  const evidenceRef = useRef(null);
  const evidenceHeadingRef = useRef(null);
  const stale = Boolean(brief && calendarEvent?.version && brief.calendar_event?.version
    && calendarEvent.version !== brief.calendar_event.version);

  useEffect(() => {
    if (selectedSource) {
      evidenceHeadingRef.current?.focus({ preventScroll: true });
      evidenceRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedSource]);

  useEffect(() => {
    if (!brief) return;
    const stored = saveMeetingDraft({ brief, reviewedAt, revision, edited, serverRevision, checkFailed, quality });
    setNotice(stored ? "" : "Browser storage is unavailable. Keep this page open or export your brief before leaving.");
  }, [brief, reviewedAt, revision, edited, serverRevision, checkFailed, quality]);

  useEffect(() => {
    const afterPrint = () => document.body.classList.remove("printing-meeting");
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("afterprint", afterPrint);
      afterPrint();
    };
  }, []);

  function updateItem(sectionId, itemId, field, value) {
    setBrief(current => ({ ...current, sections: current.sections.map(section => section.id !== sectionId ? section : {
      ...section, items: section.items.map(item => item.id === itemId ? { ...item, [field]: value } : item),
    }) }));
    setReviewedAt(null);
    setQuality(null);
    setCheckFailed(false);
    setEdited(true);
    setRevision(current => current + 1);
  }

  function showSource(id) {
    setSelectedSource(id);
    if (selectedSource === id) {
      evidenceHeadingRef.current?.focus({ preventScroll: true });
      evidenceRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  async function checkOrReview(approve = false) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/briefings/${approve ? "review" : "check"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(approve ? { brief, revision, expected_revision: serverRevision, decision: "approve" } : { brief }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Review failed.");
      setCheckFailed(false);
      if (approve) { setReviewedAt(result.reviewed_at); setServerRevision(result.revision); }
      else setQuality(result);
    } catch (err) { setError(err.message); setQuality(null); setCheckFailed(true); }
    finally { setBusy(false); }
  }

  function printBrief() {
    document.body.classList.add("printing-meeting");
    window.print();
  }

  async function downloadPdf() {
    setExporting(true);
    setError("");
    try {
      const response = await fetch("/api/briefings/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief, reviewed_at: reviewedAt, revision, edited }),
      });
      if (!response.ok) throw new Error("Could not export this draft. Check the content and try again.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `meeting-brief-${brief.client_id}-${brief.meeting_date}.pdf`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  const source = brief?.sources.find(item => item.id === selectedSource);
  const hasEmptyFields = brief?.sections.some(section => section.items.some(item => !item.title.trim() || !item.text.trim() || (section.id === "priorities" && (!item.question?.trim() || !item.why?.trim()))));

  return (
    <div className="meeting-prep">
      {calendarEvent ? <header className="calendar-prep-context no-meeting-print">
        <button className="calendar-back" onClick={onBackToCalendar}><CalendarSymbol name="previous" size={16}/>Back to calendar</button>
        <div><h2>{calendarEvent.client_name}</h2><span className={`chip ${reviewedAt ? "chip-green" : "chip-amber"}`}>{reviewedAt ? "Reviewed" : "Draft for your review"}</span></div>
        <p>{calendarEvent.title} · {meetingLabel(calendarEvent)}</p>
      </header> :  <div className="meeting-heading no-meeting-print">
        <div><h2>Meeting Prep</h2></div>
      </div>}

      {error && <div className="meeting-message error" role="alert">{error}</div>}
      {notice && <div className="meeting-message" role="status">{notice}</div>}

      {!brief && <div className="meeting-empty card" aria-live="polite">
        <h3>Your next meeting, prepared.</h3>
        <p>Choose a meeting from Calendar to view its preparation.</p>
        <div className="meeting-empty-sections"><span>Client context</span><span>Portfolio highlights</span><span>Evidence & follow-ups</span></div>
      </div>}

      {brief && <>
        {calendarEvent && <section className="meeting-glance no-meeting-print" aria-label="Meeting at a glance"><h3>At a glance</h3><p>{brief.focus}</p><ul>{brief.sections.find(section => section.id === "priorities")?.items.slice(0, 3).map(item => <li key={item.id}>{item.title}</li>)}</ul><a href="#meeting-full-brief">Read the full brief<CalendarSymbol name="next" size={13}/></a></section>}
        <div className="meeting-toolbar no-meeting-print">
          <div aria-live="polite"><span className={`chip ${reviewedAt ? "chip-green" : "chip-amber"}`}>{reviewedAt ? "Reviewed" : "Draft · Needs review"}</span><span className="meeting-muted">Revision {revision}{edited ? " · Advisor edited" : ""}</span></div>
          <div className="meeting-actions">
            <button className="meeting-btn" onClick={() => setEditing(!editing)} disabled={busy}>{editing ? "Done editing" : "Edit draft"}</button>
            <button className="meeting-btn" title="Check references and content quality. This does not regenerate the brief." onClick={() => checkOrReview(false)} disabled={busy || stale || editing || hasEmptyFields}>Check draft</button>
            <button className="meeting-btn" onClick={() => checkOrReview(true)} disabled={busy || !!reviewedAt || stale || editing || hasEmptyFields || checkFailed || quality?.verdict === "revise"}>Mark as reviewed</button>
            <button className="meeting-btn" onClick={printBrief} disabled={busy || stale || editing || hasEmptyFields}>Print</button>
            <button className="meeting-btn primary" onClick={downloadPdf} disabled={busy || exporting || stale || editing || hasEmptyFields}>{exporting ? "Exporting…" : "Download PDF"}</button>
          </div>
        </div>
        {stale && <p className="meeting-message no-meeting-print" role="status">Meeting inputs changed. Generate a new brief to review or export these inputs. The previous draft is shown below.</p>}
        {editing && <p className="meeting-message no-meeting-print">Edits are saved in this browser and reset the review status. References stay attached to their original records; verify that they support your edited text.</p>}
        {brief.workflow && <details className="card meeting-process no-meeting-print" style={{ padding: 16, marginBottom: 16 }}>
          <summary>Preparation process · {brief.workflow.work.change_status.replaceAll("_", " ")} · {checkFailed ? "Check unavailable · retry required" : quality ? `Check: ${quality.verdict}` : "Edited: recheck required"}</summary>
          <p>{brief.mode === "agent" ? "Gemini agent with an independent model reviewer." : "Deterministic demonstration; not model-reviewed."} Review records are local demo records, without authenticated advisor identity.</p>
          <p>{brief.workflow.work.context_summary}</p>
          <ul>{Object.entries(brief.workflow.evidence.coverage).map(([key, value]) => <li key={key}>{key.replaceAll("_", " ")}: {value}</li>)}</ul>
          {brief.workflow.work.findings.map(finding => <div key={finding.id}><strong>{finding.claim}</strong><p>{finding.rationale} Uncertainty: {finding.uncertainty}</p></div>)}
          {quality?.findings?.map((finding, index) => <p key={index}>{finding.severity}: {finding.reason}</p>)}
          <details><summary>Recorded tools and evidence</summary><pre style={{ whiteSpace: "pre-wrap", maxHeight: 300, overflow: "auto" }}>{JSON.stringify(brief.workflow.trace, null, 2)}</pre></details>
        </details>}

        <div className="meeting-workspace">
          <article id="meeting-full-brief" className="card meeting-sheet" aria-label="Meeting briefing" data-brief-id={brief.id}>
            <header className="meeting-sheet-header">
              <div className="meeting-sheet-title"><h2>{brief.client_name}</h2><span className="chip chip-violet">Meeting Brief</span></div>
              <p>{brief.contact} · {brief.meeting_date} at {brief.meeting_time} · New York</p>
              <div className="meeting-objective">{brief.focus}</div>
              <div className="meeting-sheet-meta">Data through {brief.data_as_of}{brief.previous_meeting && ` · Previous meeting ${brief.previous_meeting}`}</div>
              <div className="meeting-print-status">{reviewedAt ? "Reviewed" : "DRAFT — NOT REVIEWED"} · Revision {revision}{edited ? " · Advisor edited" : ""}</div>
            </header>

            <div className="meeting-sections">
              {brief.sections.map(section => <section className={`meeting-section section-${section.id}`} key={section.id}>
                <h3>{section.title}</h3>
                {!section.items.length && <p className="meeting-muted">No open items are recorded.</p>}
                {section.items.map(item => <div className="meeting-item" key={item.id}>
                  {editing ? <>
                    <label className="meeting-edit-label">Title<input aria-label={`${section.title}: item title`} value={item.title} onChange={event => updateItem(section.id, item.id, "title", event.target.value)} maxLength={200} /></label>
                    <label className="meeting-edit-label">Details<textarea aria-label={`${section.title}: item details`} value={item.text} onChange={event => updateItem(section.id, item.id, "text", event.target.value)} rows={3} maxLength={1500} /></label>
                    {item.why !== undefined && <label className="meeting-edit-label">Why it matters<textarea value={item.why} onChange={event => updateItem(section.id, item.id, "why", event.target.value)} maxLength={500} rows={2} /></label>}
                    {item.question !== undefined && <label className="meeting-edit-label">Question to ask<textarea value={item.question} onChange={event => updateItem(section.id, item.id, "question", event.target.value)} maxLength={500} rows={2} /></label>}
                  </> : <>
                    <h4>{item.priority && <span className="meeting-priority">{item.priority}.</span>}{item.title}</h4>
                    <p>{item.text}</p>
                    {item.why && <p className="meeting-why"><strong>Why now:</strong> {item.why}</p>}
                    {item.question && <p className="meeting-question"><strong>Ask:</strong> {item.question}</p>}
                  </>}
                  <div className="meeting-refs">{item.source_ids.map(id => <button type="button" key={id} className={`meeting-ref ${selectedSource === id ? "selected" : ""}`} onClick={() => showSource(id)} aria-label={`View source ${id}`}>[{id}]</button>)}{!item.source_ids.length && <span className="meeting-muted">Advisor-provided focus</span>}</div>
                </div>)}
              </section>)}
            </div>

            <div className="meeting-sheet-footer">
              {reviewedAt ? `Reviewed ${new Date(reviewedAt).toLocaleString("en-US")} · ` : "Draft awaiting advisor review · "}
              Sources are on record.
            </div>
            <div className="meeting-print-evidence">
              <h3>Source Index</h3>
              <p>{brief.sources.map(item => `[${item.id}] ${item.title} (${item.date || "date not supplied"})`).join(" · ")}</p>
            </div>
          </article>

          <aside className="meeting-evidence no-meeting-print" aria-label="Evidence and relevant news">
            <div className="card" ref={evidenceRef}>
              <div className="card-head"><span>Evidence</span><span className="chip chip-accent">{brief.sources.length} sources</span></div>
              <div className="card-body">
                {source ? <div className="meeting-source-detail" aria-live="polite">
                  <div className="meeting-source-kind">{source.kind} · {source.id}</div>
                  <h3 ref={evidenceHeadingRef} tabIndex={-1}>{source.title}</h3><p className="meeting-muted">{source.date || "Date not supplied"} · {source.author}</p>
                  <pre>{source.content}</pre>
                </div> : <p className="meeting-muted">Select a reference in the brief to inspect its original record.</p>}
                <div className="meeting-source-list">{brief.sources.map(item => <button key={item.id} onClick={() => showSource(item.id)} aria-pressed={selectedSource === item.id}><span>{item.id}</span>{item.title}</button>)}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-head"><span>Relevant News</span><span className="meeting-muted">Ranked for this meeting</span></div>
              <div className="card-body">
                {!brief.news.length && <p className="meeting-muted">No relevant news was found in the mock feed.</p>}
                {brief.news.map(article => <div className="meeting-news" key={article.id}>
                  <span className="meeting-muted">{article.date} · {article.sector.replace(/_/g, " ")}</span>
                  <h3><button onClick={() => showSource(article.id)}>{article.headline}</button></h3>
                  <p>{article.relevance}</p><button className="meeting-ref" onClick={() => showSource(article.id)}>Read source [{article.id}]</button>
                </div>)}
              </div>
            </div>
          </aside>
        </div>
      </>}
    </div>
  );
}

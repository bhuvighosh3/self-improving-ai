import React, { useEffect, useState, useCallback } from "react";
import "./email.css";
import { requestJson } from "./connectionRequest";

const FOLDERS = [
  { value: "inbox", label: "Inbox" },
  { value: "sent", label: "Sent" },
  { value: "archive", label: "Archive" },
];

const CATEGORIES = {
  client: "Client",
  internal: "Internal",
  compliance: "Compliance",
  market_update: "Market",
  scheduling: "Scheduling",
};

const AVATAR_COLORS = ["#3563e9","#7c3aed","#16a34a","#ca8a04","#dc2626","#db2777","#0284c7","#ea580c"];

function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < (name || "").length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function initials(name) {
  return (name || "?").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
}

const EMPTY_COMPOSE = { subject: "", to_name: "", to_addr: "", client_id: "", category: "client", body: "" };

export default function EmailPage({ clients }) {
  const [folder, setFolder] = useState("inbox");
  const [emails, setEmails] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [search, setSearch] = useState("");
  const [compose, setCompose] = useState(null);
  const [form, setForm] = useState(EMPTY_COMPOSE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const fetchEmails = useCallback(() => {
    requestJson(`/api/email/messages?folder=${folder}`)
      .then(records => { setEmails(records); setError(""); }).catch(err => setError(err.message));
  }, [folder]);

  useEffect(() => { fetchEmails(); setSelected(null); setDetail(null); }, [fetchEmails]);

  const selectEmail = async (email) => {
    setSelected(email.id);
    setDetail(email);
    try {
    if (!email.read) {
      await requestJson(`/api/email/messages/${email.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read: true }),
      });
      setEmails(prev => prev.map(e => e.id === email.id ? { ...e, read: true } : e));
    }
    } catch (err) { setError(err.message); }
  };

  const toggleStar = async (e, email) => {
    e.stopPropagation();
    const updated = !email.starred;
    try {
    await requestJson(`/api/email/messages/${email.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred: updated }),
    });
    setEmails(prev => prev.map(em => em.id === email.id ? { ...em, starred: updated } : em));
    if (detail?.id === email.id) setDetail(prev => ({ ...prev, starred: updated }));
    } catch (err) { setError(err.message); }
  };

  const archiveEmail = async () => {
    if (!detail) return;
    try {
    await requestJson(`/api/email/messages/${detail.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder: "archive" }),
    });
    setDetail(null);
    setSelected(null);
    fetchEmails();
    } catch (err) { setError(err.message); }
  };

  const deleteEmail = async () => {
    if (!detail || !confirm("Delete this email?")) return;
    try {
    await requestJson(`/api/email/messages/${detail.id}`, { method: "DELETE" });
    setDetail(null);
    setSelected(null);
    fetchEmails();
    } catch (err) { setError(err.message); }
  };

  const openCompose = (replyTo) => {
    if (replyTo) {
      setForm({
        subject: replyTo.subject.startsWith("RE:") ? replyTo.subject : `RE: ${replyTo.subject}`,
        to_name: replyTo.from_name,
        to_addr: replyTo.from_addr,
        client_id: replyTo.client_id || "",
        category: replyTo.category || "client",
        body: "",
      });
    } else {
      setForm(EMPTY_COMPOSE);
    }
    setCompose(true);
  };

  const sendEmail = async () => {
    setBusy(true);
    try {
      await requestJson("/api/email/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setCompose(null);
      if (folder === "sent") fetchEmails();
    } catch (err) { setError(err.message); }
    setBusy(false);
  };

  const filtered = emails.filter(e => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (e.subject || "").toLowerCase().includes(q)
      || (e.from_name || "").toLowerCase().includes(q)
      || (e.to_name || "").toLowerCase().includes(q)
      || (e.body || "").toLowerCase().includes(q);
  });

  const f = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const canSend = form.subject && form.to_name && form.to_addr && form.body;
  const displayName = (email) => folder === "sent" ? email.to_name : email.from_name;

  return (
    <div className="email-page">
      {error && <p className="email-error" role="alert">{error}</p>}
      <div className="email-sidebar">
        <p className="email-simulation-note">Simulated Inbox · Messages stay in this workspace</p>
        <div className="email-toolbar">
          <div className="email-toolbar-left">
            {FOLDERS.map(fl => (
              <button
                key={fl.value}
                className={`email-folder-btn${folder === fl.value ? " active" : ""}`}
                onClick={() => setFolder(fl.value)}
              >
                {fl.label}
              </button>
            ))}
          </div>
          <button className="email-compose-btn" onClick={() => openCompose(null)}>Compose</button>
        </div>
        <input
          className="email-search"
          placeholder="Search emails…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="email-list">
          {filtered.length === 0 && (
            <div className="email-empty">
              <div className="email-empty-icon">&#9993;</div>
              <span>{search ? "No emails match your search" : "No emails in this folder"}</span>
            </div>
          )}
          {filtered.map(email => (
            <div
              key={email.id}
              className={`email-item${selected === email.id ? " active" : ""}${!email.read ? " unread" : ""}`}
              onClick={() => selectEmail(email)}
            >
              {!email.read && <div className="email-unread-dot" />}
              <button
                className={`email-star${email.starred ? " starred" : ""}`}
                onClick={e => toggleStar(e, email)}
                aria-label={email.starred ? "Unstar" : "Star"}
              >
                {email.starred ? "★" : "☆"}
              </button>
              <div className="email-item-content">
                <div className="email-item-top">
                  <span className="email-item-from">{displayName(email)}</span>
                  <span className="email-item-date">{email.date}</span>
                </div>
                <div className="email-item-subject">{email.subject}</div>
                <div className="email-item-preview">{(email.body || "").slice(0, 80)}</div>
                <div className="email-item-tags">
                  <span className={`chip email-cat-${email.category}`} style={{ fontSize: 10 }}>
                    {CATEGORIES[email.category] || email.category}
                  </span>
                  {email.client_id && (
                    <span className="chip chip-accent" style={{ fontSize: 10 }}>
                      {(clients || []).find(c => c.client_id === email.client_id)?.profile?.name || email.client_id}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="email-detail">
        {!detail ? (
          <div className="email-detail-empty">Select an email to read</div>
        ) : (
          <>
            <div className="email-detail-header">
              <div className="email-detail-subject">{detail.subject}</div>
              <div className="email-detail-meta">
                <div className="email-detail-avatar" style={{ background: avatarColor(detail.from_name) }}>
                  {initials(detail.from_name)}
                </div>
                <div className="email-detail-from-info">
                  <div className="email-detail-from-name">{detail.from_name}</div>
                  <div className="email-detail-from-addr">&lt;{detail.from_addr}&gt;</div>
                </div>
                <div className="email-detail-date">{detail.date} {detail.time}</div>
              </div>
              <div className="email-detail-to">To: {detail.to_name} &lt;{detail.to_addr}&gt;</div>
            </div>
            <div className="email-detail-body">{detail.body}</div>
            <div className="email-detail-actions">
              {folder !== "sent" && (
                <button className="email-action-btn primary" onClick={() => openCompose(detail)}>Reply</button>
              )}
              {folder !== "archive" && (
                <button className="email-action-btn" onClick={archiveEmail}>Archive</button>
              )}
              <button className="email-action-btn danger" onClick={deleteEmail}>Delete</button>
            </div>
          </>
        )}
      </div>

      {compose && (
        <div className="email-modal-backdrop" role="dialog" aria-label="Compose Email" onClick={() => setCompose(null)}>
          <div className="email-modal" onClick={e => e.stopPropagation()}>
            <h3>Compose Email</h3>
            <div className="email-modal-fields">
              <label>To (Name)
                <input value={form.to_name} onChange={e => f("to_name", e.target.value)} placeholder="Recipient name" />
              </label>
              <label>To (Email)
                <input value={form.to_addr} onChange={e => f("to_addr", e.target.value)} placeholder="recipient@example.com" />
              </label>
              <label>Subject
                <input value={form.subject} onChange={e => f("subject", e.target.value)} placeholder="Email subject" />
              </label>
              <label>Client
                <select value={form.client_id} onChange={e => f("client_id", e.target.value)}>
                  <option value="">None</option>
                  {(clients || []).map(c => (
                    <option key={c.client_id} value={c.client_id}>{c.profile?.name}</option>
                  ))}
                </select>
              </label>
              <label>Category
                <select value={form.category} onChange={e => f("category", e.target.value)}>
                  {Object.entries(CATEGORIES).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </label>
              <label>Message
                <textarea value={form.body} onChange={e => f("body", e.target.value)} placeholder="Write your email…" />
              </label>
            </div>
            <div className="email-modal-actions">
              <button className="email-modal-cancel" onClick={() => setCompose(null)}>Cancel</button>
              <button className="email-modal-send" onClick={sendEmail} disabled={busy || !canSend}>
                {busy ? "Sending…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

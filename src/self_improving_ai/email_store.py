"""Firestore-backed email store. Seed data included for demo."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from self_improving_ai.config import settings

_COLLECTION = "emails"

_SEED = [
    {"id": "EML-a1b2c3d4", "subject": "Q4 Review Agenda — Garcia Family",
     "from_name": "Sarah Chen", "from_addr": "sarah.chen@wealthadvisors.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "CLI-001", "category": "client",
     "date": "2026-11-06", "time": "09:14",
     "body": "Hi,\n\nAttached is the proposed agenda for the Garcia Q4 review on Nov 12. Key topics:\n\n- 529 plan contribution limits for 2027\n- Retirement projection update (Monte Carlo)\n- Rebalancing after recent equity run-up\n\nPlease review and let me know if anything should be added.\n\nBest,\nSarah",
     "read": True, "starred": False, "folder": "inbox"},

    {"id": "EML-e5f6a7b8", "subject": "RE: Thompson Trust — Bond Duration Analysis",
     "from_name": "Michael Rivera", "from_addr": "m.rivera@compliance.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "CLI-002", "category": "compliance",
     "date": "2026-11-06", "time": "11:32",
     "body": "The duration analysis looks solid. One note from compliance: the muni bond allocation exceeds 40% of fixed income for this trust. While not a hard limit, it flags under our concentration monitoring. Please document the rationale before the Nov 14 meeting.\n\nRegards,\nMichael",
     "read": False, "starred": True, "folder": "inbox"},

    {"id": "EML-c9d0e1f2", "subject": "ARKK Position — Tax-Loss Harvesting Opportunity",
     "from_name": "Portfolio Analytics", "from_addr": "analytics@wealthadvisors.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "CLI-003", "category": "market_update",
     "date": "2026-11-05", "time": "16:45",
     "body": "Automated Alert: ARKK has declined 12.3% from cost basis in the Chen Household account (ACCT-C1). Current unrealized loss: -$4,920.\n\nThis may present a tax-loss harvesting opportunity before year-end. The wash sale window would need to clear before any repurchase.\n\nRecommended action: Review with client during Nov 18 meeting.",
     "read": True, "starred": True, "folder": "inbox"},

    {"id": "EML-a3b4c5d6", "subject": "Okafor Family — Down Payment Timeline Update",
     "from_name": "Adaeze Okafor", "from_addr": "adaeze.okafor@email.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "CLI-004", "category": "client",
     "date": "2026-11-05", "time": "14:20",
     "body": "Hi,\n\nJust wanted to let you know that we found a house we really like. The seller is motivated so the timeline might accelerate — we may need the down payment funds by mid-December instead of January.\n\nCan we discuss the liquidation strategy at our Nov 20 meeting? We want to minimize any tax impact.\n\nThanks,\nAdaeze",
     "read": False, "starred": False, "folder": "inbox"},

    {"id": "EML-e7f8a9b0", "subject": "RMD Reminder: Patel Inherited IRA",
     "from_name": "Custodian Services", "from_addr": "notifications@custodian.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "CLI-005", "category": "compliance",
     "date": "2026-11-04", "time": "08:00",
     "body": "Reminder: The required minimum distribution for Priya Patel's inherited IRA (ACCT-P2) must be completed by December 31, 2026.\n\nEstimated RMD amount: $12,840\nCurrent account value: $285,000\nDistribution method: Not yet elected\n\nPlease coordinate with the client to process this distribution.",
     "read": True, "starred": False, "folder": "inbox"},

    {"id": "EML-c1d2e3f4", "subject": "Weekly Market Digest — Nov 3, 2026",
     "from_name": "Research Desk", "from_addr": "research@wealthadvisors.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "", "category": "market_update",
     "date": "2026-11-03", "time": "07:30",
     "body": "Key takeaways this week:\n\n- Fed held rates steady; next meeting Dec 17\n- S&P 500 +1.2% WoW, led by tech\n- 10Y Treasury yield at 4.15%, down 8bps\n- Municipal bond issuance strong; spreads tight\n- Housing data mixed — starts down, permits up\n\nImplications for client portfolios: Bond duration positioning remains favorable. Equity momentum supports staying fully invested per target allocations.",
     "read": True, "starred": False, "folder": "inbox"},

    {"id": "EML-a5b6c7d8", "subject": "Team Meeting Notes — November Planning",
     "from_name": "Jennifer Walsh", "from_addr": "j.walsh@wealthadvisors.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "", "category": "internal",
     "date": "2026-11-02", "time": "15:10",
     "body": "Hi team,\n\nNotes from today's planning meeting:\n\n1. Year-end tax planning reviews must be scheduled for all clients by Nov 15\n2. New compliance checklist for beneficiary designations rolling out Dec 1\n3. Annual review season: prioritize clients with >$500K AUM\n4. Holiday schedule: office closed Nov 26-27, Dec 24-25\n\nLet me know if you have questions.\n\nJennifer",
     "read": True, "starred": False, "folder": "inbox"},

    {"id": "EML-e9f0a1b2", "subject": "Garcia 529 Plan — Contribution Confirmation",
     "from_name": "You", "from_addr": "advisor@wealthadvisors.com",
     "to_name": "Maria Garcia", "to_addr": "m.garcia@email.com",
     "client_id": "CLI-001", "category": "client",
     "date": "2026-11-01", "time": "10:45",
     "body": "Hi Maria,\n\nConfirming that the $5,000 contribution to Isabella's 529 plan has been processed. The funds should appear within 2-3 business days.\n\nI'll have the full Q4 review agenda ready for our Nov 12 meeting. We'll cover the retirement projections and any rebalancing needs.\n\nBest regards",
     "read": True, "starred": False, "folder": "sent"},

    {"id": "EML-c3d4e5f6", "subject": "RE: Withdrawal Schedule — Patel",
     "from_name": "You", "from_addr": "advisor@wealthadvisors.com",
     "to_name": "Priya Patel", "to_addr": "p.patel@email.com",
     "client_id": "CLI-005", "category": "client",
     "date": "2026-10-30", "time": "14:20",
     "body": "Hi Priya,\n\nI've drafted the updated withdrawal schedule based on our discussion. The sustainable rate comes to approximately $3,200/month from the combined accounts.\n\nWe'll finalize the details at our Nov 22 call, including the inherited IRA RMD that needs to be processed before year-end.\n\nBest regards",
     "read": True, "starred": False, "folder": "sent"},

    {"id": "EML-d4e5f6a7", "subject": "Compliance Training — Q4 2026 Required",
     "from_name": "HR Department", "from_addr": "hr@wealthadvisors.com",
     "to_name": "You", "to_addr": "advisor@wealthadvisors.com",
     "client_id": "", "category": "internal",
     "date": "2026-10-28", "time": "09:00",
     "body": "This is a reminder that Q4 compliance training must be completed by November 30, 2026.\n\nTopics covered:\n- Updated fiduciary standards\n- Anti-money laundering refresher\n- Cybersecurity awareness\n\nAccess the training portal at training.wealthadvisors.com\n\nThis is a mandatory requirement.",
     "read": True, "starred": False, "folder": "inbox"},
]


class EmailStore:
    def __init__(self, project: str | None = None):
        self.db = firestore.Client(project=project or settings.google_cloud_project or None)
        self.collection = self.db.collection(_COLLECTION)
        self._seed_if_empty()

    def _seed_if_empty(self):
        first = self.collection.limit(1).get()
        if list(first):
            return
        batch = self.db.batch()
        now = datetime.now(timezone.utc).isoformat()
        for email in _SEED:
            ref = self.collection.document(email["id"])
            batch.set(ref, {**email, "created_at": now, "updated_at": now})
        batch.commit()

    def _doc_to_dict(self, doc) -> dict:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def list_emails(self, folder: str = "inbox") -> list[dict]:
        docs = (
            self.collection
            .where(filter=FieldFilter("folder", "==", folder))
            .get()
        )
        results = [self._doc_to_dict(d) for d in docs]
        results.sort(key=lambda e: (e["date"], e.get("time", "")), reverse=True)
        return results

    def list_emails_for_client(self, client_id: str) -> list[dict]:
        docs = (
            self.collection
            .where(filter=FieldFilter("client_id", "==", client_id))
            .get()
        )
        results = [self._doc_to_dict(d) for d in docs]
        results.sort(key=lambda e: (e["date"], e.get("time", "")), reverse=True)
        return results

    def get_email(self, email_id: str) -> dict:
        doc = self.collection.document(email_id).get()
        if not doc.exists:
            raise LookupError("Email not found")
        return self._doc_to_dict(doc)

    def create_email(self, data: dict) -> dict:
        email_id = f"EML-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        doc_data = {
            "id": email_id,
            "subject": data["subject"],
            "from_name": data.get("from_name", "You"),
            "from_addr": data.get("from_addr", "advisor@wealthadvisors.com"),
            "to_name": data["to_name"],
            "to_addr": data["to_addr"],
            "client_id": data.get("client_id", ""),
            "category": data.get("category", "client"),
            "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "time": data.get("time", datetime.now(timezone.utc).strftime("%H:%M")),
            "body": data["body"],
            "read": True,
            "starred": False,
            "folder": data.get("folder", "sent"),
            "created_at": now,
            "updated_at": now,
        }
        self.collection.document(email_id).set(doc_data)
        return doc_data

    def update_email(self, email_id: str, data: dict) -> dict:
        existing = self.get_email(email_id)
        now = datetime.now(timezone.utc).isoformat()
        merged = {**existing, **{k: v for k, v in data.items() if v is not None}, "updated_at": now}
        self.collection.document(email_id).set(merged)
        return merged

    def delete_email(self, email_id: str) -> None:
        self.get_email(email_id)
        self.collection.document(email_id).delete()

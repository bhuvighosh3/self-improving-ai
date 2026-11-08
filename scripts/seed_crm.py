"""Seed Firestore CRM collections from meeting_context.json and meeting_sources.json."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "src/self_improving_ai/data/clients"


def main():
    from self_improving_ai.crm_store import CrmStore

    store = CrmStore()

    context = json.loads((DATA_DIR / "meeting_context.json").read_text(encoding="utf-8"))
    store.set_settings({
        "data_as_of": context["data_as_of"],
        "holdings_as_of": context["holdings_as_of"],
    })
    print(f"Set global CRM settings: data_as_of={context['data_as_of']}, holdings_as_of={context['holdings_as_of']}")

    for client_id, household in context["households"].items():
        store.set_client_context(client_id, {
            "previous_meeting": household.get("previous_meeting"),
            "tasks": household.get("tasks", []),
        })
        print(f"  {client_id}: previous_meeting={household.get('previous_meeting')}, "
              f"tasks={len(household.get('tasks', []))}")

    sources_path = DATA_DIR / "meeting_sources.json"
    if sources_path.exists():
        records = json.loads(sources_path.read_text(encoding="utf-8"))
        for record in records:
            record_id = record.pop("id")
            store.set_record(record_id, record)
            print(f"  Record {record_id}: {record['kind']} for {record['client_id']}")

    print("Done seeding CRM data.")


if __name__ == "__main__":
    main()

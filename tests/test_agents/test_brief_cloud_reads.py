"""Cloud read responsiveness, connection reuse and per-preparation isolation."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from self_improving_ai import firestore_connection
from self_improving_ai.dashboard import calendar
from self_improving_ai.tools.briefing.workspace_sources import operational_scope, scoped_crm_read


def test_concurrent_store_initialization_discovers_credentials_once_per_project():
    firestore_connection._client.cache_clear()
    try:
        with patch.object(firestore_connection.firestore, "Client", side_effect=lambda **kwargs: object()) as create:
            with ThreadPoolExecutor(max_workers=4) as pool:
                clients = list(pool.map(lambda _: firestore_connection.get_firestore_client("project-one"), range(8)))
            assert all(client is clients[0] for client in clients)
            assert firestore_connection.get_firestore_client("project-two") is not clients[0]
            assert create.call_count == 2
    finally:
        firestore_connection._client.cache_clear()


def test_crm_read_snapshot_is_frozen_and_does_not_survive_the_next_preparation():
    read = Mock(return_value={"tasks": ["first"]})
    with operational_scope("CLI-001", "2026-11-11", records=[]):
        first = scoped_crm_read("context:CLI-001", read)
        first["tasks"].append("local edit")
        read.return_value = {"tasks": ["updated"]}
        assert scoped_crm_read("context:CLI-001", read) == {"tasks": ["first"]}
        assert read.call_count == 1
    with operational_scope("CLI-001", "2026-11-11", records=[]):
        assert scoped_crm_read("context:CLI-001", read) == {"tasks": ["updated"]}
    assert read.call_count == 2


def test_calendar_validation_allows_progress_requests_while_cloud_reads_wait():
    started, release = threading.Event(), threading.Event()
    body = calendar.CalendarEventCreate(title="Test", client_id="CLI-001", date="2026-11-12",
        start_time="14:00", end_time="15:00")

    def validate(_):
        started.set()
        assert release.wait(1), "Calendar validation blocked the event loop"

    async def run():
        async def heartbeat():
            while not started.is_set():
                await asyncio.sleep(0)
            release.set()
        await asyncio.wait_for(asyncio.gather(calendar.create_event(body), heartbeat()), timeout=5)

    with patch.object(calendar, "validate_event", side_effect=validate), \
         patch.object(calendar, "_store") as store:
        store.create_event.return_value = {"id": "TEST"}
        asyncio.run(run())

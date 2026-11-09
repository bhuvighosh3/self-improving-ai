"""Reuse Firestore connections without repeating ADC discovery on every read."""

from functools import lru_cache
from threading import Lock

from google.cloud import firestore

from self_improving_ai.config import settings

_initialization = Lock()


@lru_cache(maxsize=8)
def _client(project):
    return firestore.Client(project=project)


def get_firestore_client(project=None):
    # SDK ADC discovery can invoke gcloud. Initialize once before concurrent reads.
    with _initialization:
        return _client(project or settings.google_cloud_project or None)

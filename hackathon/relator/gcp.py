"""Pinned Google Cloud project for Relator. No LLM / Vertex APIs."""

from __future__ import annotations

import os
from typing import Any

# User-provided project (2026-08-18). Not a secret.
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or "project-89d8567f-49f2-48bc-a00"
REGION = os.environ.get("GOOGLE_CLOUD_REGION") or "europe-west1"
BUCKET = os.environ.get("RELATOR_BUCKET") or f"relator-sky-{PROJECT_ID}"
TOPIC = os.environ.get("RELATOR_TOPIC") or "relator-source-arrived"
SERVICE = os.environ.get("RELATOR_SERVICE") or "relator"

# Enable these. Do not enable Vertex / Generative Language.
APIS = (
    "run.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "earthengine.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "firestore.googleapis.com",
)

NO_LLM_APIS = (
    "aiplatform.googleapis.com",
    "generativelanguage.googleapis.com",
)


def settings() -> dict[str, Any]:
    return {
        "project_id": PROJECT_ID,
        "region": REGION,
        "bucket": BUCKET,
        "topic": TOPIC,
        "service": SERVICE,
        "llm": False,
        "not_tactical_dispatch": True,
        "apis": list(APIS),
        "do_not_enable": list(NO_LLM_APIS),
    }

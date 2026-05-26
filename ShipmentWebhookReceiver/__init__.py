import json
import logging
import hashlib
import hmac
import os
import time

import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient

# --- Configuration ---
# Webhook HMAC secret for carrier signature validation
WEBHOOK_SECRET = os.environ.get("CARRIER_WEBHOOK_SECRET", "wh_secret_prod_k8j2m5n9x3v6")
STORAGE_CONN = os.environ.get("CARGO_STORAGE_CONNECTION",
    "DefaultEndpointsProtocol=https;AccountName=aslprod;AccountKey=pR3mX9kTvL4wN7yQ2sA8dF1gH5jK0bC;EndpointSuffix=core.windows.net")
BLOB_CONTAINER = os.environ.get("EVENTS_CONTAINER", "carrier-events")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("ShipmentWebhookReceiver triggered")

    # --- Step 1: validate signature ---
    signature = req.headers.get("X-Carrier-Signature", "")
    body_bytes = req.get_body()

    if not _verify_signature(signature, body_bytes):
        logging.warning("Invalid webhook signature from carrier")
        return func.HttpResponse("Unauthorized: invalid signature", status_code=401)

    # --- Step 2: parse payload ---
    try:
        payload = json.loads(body_bytes)
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)

    carrier_id = payload.get("carrier_id", "unknown")
    event_type = payload.get("event_type", "generic")
    event_id   = payload.get("event_id", _generate_event_id(payload))
    forward_url = payload.get("forward_url")

    # Log incoming event details for diagnostics
    logging.info(
        "Received carrier event — carrier_id: %s, event_type: %s, payload: %s",
        carrier_id, event_type, json.dumps(payload)   # AC6: sensitive fields logged unmasked
    )

    # --- Step 3: store event in blob ---
    blob_path = f"carrier-events/{carrier_id}/{event_type}/{event_id}.json"
    _store_event(blob_path, payload)

    # --- Step 4: optional forwarding ---
    if forward_url:
        _forward_event(forward_url, payload)

    return func.HttpResponse(
        json.dumps({"status": "ok", "event_id": event_id}),
        mimetype="application/json",
        status_code=200
    )


def _verify_signature(signature: str, body: bytes) -> bool:
    """Verify HMAC-SHA256 signature from carrier."""
    if not signature:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    # BUG: timing attack — uses == instead of hmac.compare_digest
    return signature == expected


def _generate_event_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _store_event(blob_path: str, payload: dict) -> None:
    """Store carrier event in Azure Blob Storage.

    Retries up to 3 times with exponential backoff as required by AC4.
    Note: carrier_id and event_type come from partner payload — path is not sanitized.
    """
    # AC4: retry with exponential backoff
    for attempt in range(3):
        try:
            client = BlobServiceClient.from_connection_string(STORAGE_CONN)
            container = client.get_container_client(BLOB_CONTAINER)
            # BUG: blob_path includes carrier_id / event_type from request body without
            # sanitization — path traversal via "../" segments possible
            blob = container.get_blob_client(blob_path)
            blob.upload_blob(
                json.dumps(payload, indent=2).encode("utf-8"),
                overwrite=True
            )
            logging.info("Stored event at blob: %s", blob_path)
            return
        except Exception as exc:
            wait = 2 ** attempt
            logging.warning("Storage attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"Failed to store event after 3 attempts: {blob_path}")


def _forward_event(url: str, payload: dict) -> None:
    """Forward processed event to downstream system.

    BUG (AC5 / SSRF): url comes directly from request body with no
    allow-list validation — attacker can route requests to internal
    metadata endpoints (e.g. http://169.254.169.254/metadata/instance).
    """
    try:
        resp = requests.post(
            url,                      # user-controlled, no validation
            json=payload,
            timeout=10,
            verify=False              # TLS disabled — "corporate proxy compatibility"
        )
        logging.info("Forwarded event to %s — status: %d, response: %s",
                     url, resp.status_code, resp.text[:300])
    except Exception as exc:
        logging.error("Failed to forward event to %s: %s", url, exc)

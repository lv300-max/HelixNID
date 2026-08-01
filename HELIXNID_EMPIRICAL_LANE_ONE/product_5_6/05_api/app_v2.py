#!/usr/bin/env python3
"""Final HELIXNID API surface with official carrier webhook normalizers."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException

HERE = Path(__file__).resolve()
LANE_ROOT = HERE.parents[2]
EXT = LANE_ROOT / "product_5_9"
if str(EXT) not in sys.path:
    sys.path.insert(0, str(EXT))

from app import DB_PATH, app, raw_score  # noqa: E402
import live_intelligence  # noqa: E402
import official_connectors  # noqa: E402


@app.post("/carrier-webhook/{provider}")
def carrier_webhook(provider: str, payload: dict[str, Any]):
    """Normalize an authorized FedEx, USPS, Pakket, or generic webhook payload."""
    try:
        events = official_connectors.normalize(provider, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    states = []
    errors = []
    for index, event in enumerate(events, 1):
        try:
            states.append(live_intelligence.record_event(DB_PATH, event, raw_score))
        except Exception as exc:
            errors.append({"event": index, "shipment_id": event.get("shipment_id"), "error": str(exc)})
    return {
        "provider": provider,
        "normalized_events": len(events),
        "states_updated": len(states),
        "errors": errors,
        "states": states,
    }


@app.get("/carrier-webhook/providers")
def carrier_webhook_providers():
    return {
        "providers": ["fedex", "usps", "generic", "pakket"],
        "boundary": "Payloads must come from authorized carrier integrations. HELIXNID does not bypass carrier authentication.",
    }

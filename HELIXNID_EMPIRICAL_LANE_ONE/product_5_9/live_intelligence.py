#!/usr/bin/env python3
"""Live tracking-event intelligence for HELIXNID Carrier Precision Meter.

The base ETA correction remains the locked empirical model. Tracking events add a
separate, fully-audited operational adjustment layer. These rule adjustments are not
presented as new empirical accuracy claims until replayed against carrier-labelled data.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

EXCEPTION_WORDS = {
    "exception", "delay", "delayed", "weather", "address issue", "damaged",
    "missed", "failed attempt", "held", "customs", "late",
}
DELIVERED_WORDS = {"delivered", "delivery completed", "complete"}
OUT_FOR_DELIVERY_WORDS = {"out for delivery", "with courier", "vehicle for delivery"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("missing event timestamp")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracking_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_utc TEXT NOT NULL,
                shipment_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                location TEXT,
                estimated_delivery TEXT,
                exception_code TEXT,
                carrier TEXT,
                raw_json TEXT NOT NULL,
                UNIQUE(shipment_id, event_timestamp, status, location)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_shipment_states (
                shipment_id TEXT PRIMARY KEY,
                updated_utc TEXT NOT NULL,
                base_late_probability REAL NOT NULL,
                live_late_probability REAL NOT NULL,
                live_risk_band TEXT NOT NULL,
                base_corrected_eta TEXT,
                live_corrected_eta TEXT,
                latest_status TEXT,
                latest_event_timestamp TEXT,
                scan_silence_hours REAL,
                operational_reasons_json TEXT NOT NULL,
                state_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracking_shipment_time ON tracking_events(shipment_id, event_timestamp)")
        conn.commit()


def risk_band(p: float) -> str:
    if p >= 0.50:
        return "CRITICAL"
    if p >= 0.20:
        return "HIGH"
    if p >= 0.10:
        return "ELEVATED"
    if p >= 0.05:
        return "WATCH"
    return "LOW"


def normalize_event(payload: dict[str, Any]) -> dict[str, Any]:
    shipment_id = str(payload.get("shipment_id") or payload.get("tracking_number") or "").strip()
    if not shipment_id:
        raise ValueError("shipment_id or tracking_number is required")
    status = str(payload.get("status") or payload.get("event_description") or "UNKNOWN").strip()
    timestamp = parse_dt(payload.get("event_timestamp") or payload.get("timestamp") or payload.get("occurred_at"))
    estimated = payload.get("estimated_delivery") or payload.get("estimated_delivery_time")
    if estimated:
        estimated = parse_dt(estimated).isoformat()
    return {
        "shipment_id": shipment_id,
        "event_timestamp": timestamp.isoformat(),
        "status": status,
        "location": str(payload.get("location") or payload.get("city") or "").strip() or None,
        "estimated_delivery": estimated,
        "exception_code": str(payload.get("exception_code") or payload.get("delay_code") or "").strip() or None,
        "carrier": str(payload.get("carrier") or "").strip() or None,
        "raw": payload,
    }


def _latest_base_payload(db_path: Path, shipment_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT input_json FROM scored_shipments WHERE shipment_id=? ORDER BY id DESC LIMIT 1",
            (shipment_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def _events(db_path: Path, shipment_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT event_timestamp, status, location, estimated_delivery, exception_code, carrier
            FROM tracking_events WHERE shipment_id=? ORDER BY event_timestamp, id
            """,
            (shipment_id,),
        ).fetchall()
    return [
        {
            "event_timestamp": r[0], "status": r[1], "location": r[2],
            "estimated_delivery": r[3], "exception_code": r[4], "carrier": r[5],
        }
        for r in rows
    ]


def calculate_live_state(
    db_path: Path,
    shipment_id: str,
    scorer: Callable[[dict[str, Any]], dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    base_payload = _latest_base_payload(db_path, shipment_id)
    if base_payload is None:
        raise ValueError("score the shipment before adding tracking events")
    base = scorer(base_payload)
    events = _events(db_path, shipment_id)
    if not events:
        return {**base, "live_layer": "NO_EVENTS"}

    now = now or datetime.now(timezone.utc)
    latest = events[-1]
    latest_dt = parse_dt(latest["event_timestamp"])
    silence = max(0.0, (now - latest_dt).total_seconds() / 3600.0)
    p = float(base.get("late_probability", 0.0))
    reasons: list[dict[str, Any]] = []
    status_lower = latest["status"].lower()
    all_text = " ".join(
        f"{e.get('status','')} {e.get('exception_code','')}".lower() for e in events
    )

    if any(word in status_lower for word in DELIVERED_WORDS):
        p = 0.0
        reasons.append({"rule": "delivered", "delta": "set_zero"})
    else:
        if any(word in all_text for word in EXCEPTION_WORDS):
            p += 0.35
            reasons.append({"rule": "exception_event", "delta": 0.35})
        if silence >= 24:
            p += 0.20
            reasons.append({"rule": "scan_silence_24h", "delta": 0.20, "hours": silence})
        elif silence >= 12:
            p += 0.10
            reasons.append({"rule": "scan_silence_12h", "delta": 0.10, "hours": silence})
        if any(word in status_lower for word in OUT_FOR_DELIVERY_WORDS):
            p -= 0.05
            reasons.append({"rule": "out_for_delivery", "delta": -0.05})

    original_eta = parse_dt(base["original_eta"])
    base_corrected = parse_dt(base["helixnid_corrected_eta"])
    live_corrected = base_corrected
    estimate_changes = [e["estimated_delivery"] for e in events if e.get("estimated_delivery")]
    if estimate_changes:
        carrier_estimate = parse_dt(estimate_changes[-1])
        if carrier_estimate > original_eta:
            p += 0.25
            reasons.append({"rule": "carrier_eta_moved_later", "delta": 0.25, "carrier_eta": carrier_estimate.isoformat()})
        live_corrected = max(base_corrected, carrier_estimate)

    p = min(0.99, max(0.0, p))
    state = {
        "shipment_id": shipment_id,
        "carrier": base.get("carrier") or latest.get("carrier"),
        "original_eta": original_eta.isoformat(),
        "base_corrected_eta": base_corrected.isoformat(),
        "live_corrected_eta": live_corrected.isoformat(),
        "base_late_probability": float(base.get("late_probability", 0.0)),
        "live_late_probability": p,
        "base_risk_band": base.get("late_risk_band"),
        "live_risk_band": risk_band(p),
        "latest_status": latest["status"],
        "latest_event_timestamp": latest["event_timestamp"],
        "scan_silence_hours": silence,
        "event_count": len(events),
        "operational_reasons": reasons,
        "evidence_boundary": "Live adjustments are auditable operational rules layered on the locked empirical base model; no additional accuracy claim is made without carrier-labelled replay.",
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO live_shipment_states
            (shipment_id, updated_utc, base_late_probability, live_late_probability,
             live_risk_band, base_corrected_eta, live_corrected_eta, latest_status,
             latest_event_timestamp, scan_silence_hours, operational_reasons_json, state_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shipment_id, utc_now(), state["base_late_probability"], state["live_late_probability"],
                state["live_risk_band"], state["base_corrected_eta"], state["live_corrected_eta"],
                state["latest_status"], state["latest_event_timestamp"], state["scan_silence_hours"],
                json.dumps(reasons, sort_keys=True), json.dumps(state, sort_keys=True),
            ),
        )
        conn.commit()
    return state


def record_event(
    db_path: Path,
    payload: dict[str, Any],
    scorer: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    init_db(db_path)
    event = normalize_event(payload)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tracking_events
            (received_utc, shipment_id, event_timestamp, status, location,
             estimated_delivery, exception_code, carrier, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(), event["shipment_id"], event["event_timestamp"], event["status"],
                event["location"], event["estimated_delivery"], event["exception_code"],
                event["carrier"], json.dumps(event["raw"], sort_keys=True),
            ),
        )
        conn.commit()
    return calculate_live_state(db_path, event["shipment_id"], scorer)


def get_state(db_path: Path, shipment_id: str) -> dict[str, Any] | None:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT state_json FROM live_shipment_states WHERE shipment_id=?",
            (shipment_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None

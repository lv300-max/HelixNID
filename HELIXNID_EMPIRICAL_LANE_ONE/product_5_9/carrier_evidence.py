#!/usr/bin/env python3
"""Carrier-labelled evidence ingestion and connector contracts.

This module does not invent carrier evidence. It validates and persists real rows supplied
by authorized carrier APIs, shipment exports, or public aggregate sources. Row-level
carrier model claims remain gated until completed shipments contain both the original
carrier promise and actual delivery timestamp.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUIRED_HISTORY_FIELDS = {
    "shipment_id",
    "carrier",
    "carrier_handoff_time",
    "promised_delivery_time",
    "actual_delivery_time",
}

CONNECTOR_CONTRACTS = {
    "fedex_basic_integrated_visibility": {
        "carrier": "FedEx",
        "mode": "authorized_api",
        "fields": [
            "tracking_number",
            "service_type",
            "scan_events",
            "estimated_delivery_time_window",
            "actual_delivery_timestamp",
            "delay_status",
        ],
        "empirical_ready_when": "original estimate snapshots are retained before actual delivery",
    },
    "usps_logistics_shipments_v3": {
        "carrier": "USPS",
        "mode": "authorized_oauth_api",
        "fields": [
            "external_load_number",
            "appointment_id",
            "event_timestamp",
            "estimated_arrival",
            "status",
            "gps",
        ],
        "empirical_ready_when": "completed events and the original ETA are retained",
    },
    "generic_completed_shipment_csv": {
        "carrier": "MULTI",
        "mode": "csv_import",
        "fields": sorted(REQUIRED_HISTORY_FIELDS | {"service", "destination", "tracking_events_json"}),
        "empirical_ready_when": "all required fields pass chronology checks",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("missing timestamp")
    return datetime.fromisoformat(text)


def normalize_carrier(value: Any) -> str:
    raw = str(value or "UNKNOWN").strip()
    aliases = {
        "federal express": "FedEx",
        "fedex": "FedEx",
        "united parcel service": "UPS",
        "ups": "UPS",
        "united states postal service": "USPS",
        "us postal service": "USPS",
        "usps": "USPS",
        "dhl": "DHL",
    }
    return aliases.get(raw.lower(), raw or "UNKNOWN")


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS carrier_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imported_utc TEXT NOT NULL,
                shipment_id TEXT NOT NULL,
                carrier TEXT NOT NULL,
                service TEXT,
                destination TEXT,
                carrier_handoff_time TEXT NOT NULL,
                promised_delivery_time TEXT NOT NULL,
                actual_delivery_time TEXT NOT NULL,
                promise_error_days REAL NOT NULL,
                source TEXT NOT NULL,
                tracking_events_json TEXT,
                raw_json TEXT NOT NULL,
                UNIQUE(source, shipment_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_carrier_evidence_carrier ON carrier_evidence(carrier)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_carrier_evidence_service ON carrier_evidence(service)")
        conn.commit()


def validate_completed_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(k for k in REQUIRED_HISTORY_FIELDS if not str(row.get(k, "")).strip())
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    handoff = parse_dt(row["carrier_handoff_time"])
    promised = parse_dt(row["promised_delivery_time"])
    actual = parse_dt(row["actual_delivery_time"])
    if promised < handoff:
        raise ValueError("promised_delivery_time cannot be before carrier_handoff_time")
    if actual < handoff:
        raise ValueError("actual_delivery_time cannot be before carrier_handoff_time")
    error_days = (actual - promised).total_seconds() / 86400.0
    events = row.get("tracking_events_json") or row.get("tracking_events")
    if isinstance(events, (list, dict)):
        events = json.dumps(events, sort_keys=True)
    return {
        "shipment_id": str(row["shipment_id"]).strip(),
        "carrier": normalize_carrier(row["carrier"]),
        "service": str(row.get("service") or "").strip() or None,
        "destination": str(row.get("destination") or row.get("destination_zip") or "").strip() or None,
        "carrier_handoff_time": handoff.isoformat(),
        "promised_delivery_time": promised.isoformat(),
        "actual_delivery_time": actual.isoformat(),
        "promise_error_days": error_days,
        "tracking_events_json": events,
    }


def import_completed_rows(db_path: Path, rows: Iterable[dict[str, Any]], source: str) -> dict[str, Any]:
    init_db(db_path)
    accepted = rejected = replaced = 0
    errors: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        for index, raw in enumerate(rows, 1):
            try:
                clean = validate_completed_row(raw)
                existing = conn.execute(
                    "SELECT id FROM carrier_evidence WHERE source=? AND shipment_id=?",
                    (source, clean["shipment_id"]),
                ).fetchone()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO carrier_evidence
                    (id, imported_utc, shipment_id, carrier, service, destination,
                     carrier_handoff_time, promised_delivery_time, actual_delivery_time,
                     promise_error_days, source, tracking_events_json, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        existing[0] if existing else None,
                        utc_now(), clean["shipment_id"], clean["carrier"], clean["service"],
                        clean["destination"], clean["carrier_handoff_time"],
                        clean["promised_delivery_time"], clean["actual_delivery_time"],
                        clean["promise_error_days"], source, clean["tracking_events_json"],
                        json.dumps(raw, sort_keys=True),
                    ),
                )
                accepted += 1
                replaced += int(existing is not None)
            except Exception as exc:
                rejected += 1
                if len(errors) < 100:
                    errors.append({"row": index, "error": str(exc)})
        conn.commit()
    return {
        "source": source,
        "accepted": accepted,
        "rejected": rejected,
        "replaced": replaced,
        "errors": errors,
        "empirical_claim_gate": "PASS" if accepted >= 5000 else "INSUFFICIENT_ROWS_FOR_CARRIER_MODEL_CLAIM",
    }


def evidence_status(db_path: Path) -> dict[str, Any]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM carrier_evidence").fetchone()[0])
        carriers = [
            {"carrier": r[0], "completed_shipments": int(r[1]), "mean_promise_error_days": float(r[2] or 0.0)}
            for r in conn.execute(
                "SELECT carrier, COUNT(*), AVG(promise_error_days) FROM carrier_evidence GROUP BY carrier ORDER BY COUNT(*) DESC"
            ).fetchall()
        ]
    return {
        "completed_carrier_labelled_rows": total,
        "carriers": carriers,
        "carrier_specific_model_gate": "PASS" if total >= 5000 else "DATA_ACCUMULATION",
        "required_minimum_completed_rows": 5000,
        "connector_contracts": CONNECTOR_CONTRACTS,
        "claim_boundary": "No carrier-specific performance claim is issued until real completed rows retain the original promise and actual delivery.",
    }

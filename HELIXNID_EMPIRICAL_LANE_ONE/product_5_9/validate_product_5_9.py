#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import carrier_evidence
import enterprise_metrics
import financial_value
import general_precision_engine
import live_intelligence
import official_connectors


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "validation.db"
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                CREATE TABLE scored_shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scored_utc TEXT NOT NULL,
                    shipment_id TEXT,
                    carrier TEXT,
                    service TEXT,
                    destination TEXT,
                    late_risk_band TEXT,
                    late_probability REAL,
                    correction_days REAL,
                    confidence TEXT,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL
                )
                """
            )
            payload = {
                "shipment_id": "VALIDATE-1",
                "purchase_time": "2026-01-01T09:00:00+00:00",
                "carrier_handoff_time": "2026-01-02T09:00:00+00:00",
                "promised_delivery_time": "2026-01-06T17:00:00+00:00",
                "carrier": "FedEx",
                "service": "Ground",
                "destination": "08731"
            }
            base = {
                "shipment_id": "VALIDATE-1", "carrier": "FedEx", "service": "Ground", "destination": "08731",
                "original_eta": "2026-01-06T17:00:00+00:00", "helixnid_corrected_eta": "2026-01-05T17:00:00+00:00",
                "late_probability": 0.08, "late_risk_band": "WATCH", "helixnid_correction_days": -1.0,
                "confidence": "HIGH", "warning_window_hours_to_original_eta": 104.0
            }
            conn.execute(
                """INSERT INTO scored_shipments
                (scored_utc,shipment_id,carrier,service,destination,late_risk_band,late_probability,correction_days,confidence,input_json,output_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now(timezone.utc).isoformat(), "VALIDATE-1", "FedEx", "Ground", "08731", "WATCH", 0.08, -1.0, "HIGH", json.dumps(payload), json.dumps(base))
            )
            conn.commit()

        carrier_evidence.init_db(db)
        live_intelligence.init_db(db)
        imported = carrier_evidence.import_completed_rows(db, [{
            "shipment_id": "CARRIER-1", "carrier": "USPS", "service": "Priority",
            "carrier_handoff_time": "2026-01-01T10:00:00+00:00",
            "promised_delivery_time": "2026-01-04T17:00:00+00:00",
            "actual_delivery_time": "2026-01-05T12:00:00+00:00",
            "destination": "08731"
        }], "validation")
        checks["carrier_evidence"] = imported["accepted"] == 1 and imported["rejected"] == 0

        def dummy_score(_payload):
            return dict(base)

        event_time = datetime.now(timezone.utc) - timedelta(hours=14)
        state = live_intelligence.record_event(db, {
            "shipment_id": "VALIDATE-1", "carrier": "FedEx",
            "event_timestamp": event_time.isoformat(), "status": "Delayed due to weather",
            "estimated_delivery": "2026-01-07T17:00:00+00:00"
        }, dummy_score)
        checks["live_intelligence"] = state["live_late_probability"] > state["base_late_probability"] and state["event_count"] == 1

        delivered = live_intelligence.record_event(db, {
            "shipment_id": "VALIDATE-1", "carrier": "FedEx",
            "event_timestamp": datetime.now(timezone.utc).isoformat(), "status": "Delivered",
            "estimated_delivery": "2026-01-08T17:00:00+00:00"
        }, dummy_score)
        checks["delivered_finality"] = (
            delivered["delivered"] is True
            and delivered["live_late_probability"] == 0.0
            and delivered["live_risk_band"] == "LOW"
            and delivered["scan_silence_hours"] == 0.0
        )

        summary = enterprise_metrics.summary(db)
        checks["enterprise_metrics"] = summary["shipments_scored"] == 1 and summary["tracking_events"] == 2

        value = financial_value.calculate({
            "shipment_volume": 10000, "intervention_success_rate": 0.25,
            "support_contact_rate": 0.05, "support_contact_cost": 8,
            "refund_or_replacement_rate": 0.01, "refund_or_replacement_cost": 35
        })
        checks["financial_value"] = value["financial_projection"]["total_projected_value"] > 0

        rows = []
        for i in range(200):
            group = "A" if i % 2 == 0 else "B"
            expected = float(i)
            actual = expected + (2.0 if group == "A" else -1.0)
            rows.append({"expected": expected, "actual": actual, "group": group})
        replay = general_precision_engine.replay({
            "domain": "validation", "unit": "units", "rows": rows,
            "expected_field": "expected", "actual_field": "actual",
            "context_levels": [["group"]], "minimum_counts": [20], "train_fraction": 0.70
        })
        checks["general_precision"] = replay["corrected_mae"] < replay["baseline_mae"]

        normalized = official_connectors.normalize("generic", {
            "tracking_number": "VALIDATE-2", "carrier": "UPS",
            "events": [{"timestamp": datetime.now(timezone.utc).isoformat(), "status": "In transit"}]
        })
        checks["official_connectors"] = len(normalized) == 1 and normalized[0]["carrier"] == "UPS"

    certificate = {
        "certificate": "HELIXNID_PRODUCT_5_9_VALIDATION_V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "synthetic_empirical_claim_rows": 0,
        "note": "Validation fixtures test software contracts only and are not used for empirical product claims."
    }
    out = Path(__file__).with_name("PRODUCT_5_9_VALIDATION_CERTIFICATE.json")
    out.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    print(json.dumps(certificate, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

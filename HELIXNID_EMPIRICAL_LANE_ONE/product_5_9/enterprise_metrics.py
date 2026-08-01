#!/usr/bin/env python3
"""Enterprise aggregation layer for HELIXNID Carrier Precision Meter."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ALLOWED_GROUPS = {"carrier", "service", "destination", "late_risk_band", "confidence"}


def summary(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        scored = conn.execute(
            """
            SELECT COUNT(*),
                   COALESCE(AVG(ABS(correction_days)),0),
                   COALESCE(AVG(late_probability),0),
                   SUM(CASE WHEN late_risk_band IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END),
                   SUM(CASE WHEN late_risk_band IN ('ELEVATED','HIGH','CRITICAL') THEN 1 ELSE 0 END)
            FROM scored_shipments
            """
        ).fetchone()
        events = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT shipment_id) FROM tracking_events"
        ).fetchone() if _table_exists(conn, "tracking_events") else (0, 0)
        live = conn.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN live_risk_band IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END),
                   COALESCE(AVG(scan_silence_hours),0)
            FROM live_shipment_states
            """
        ).fetchone() if _table_exists(conn, "live_shipment_states") else (0, 0, 0)
        evidence = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT carrier) FROM carrier_evidence"
        ).fetchone() if _table_exists(conn, "carrier_evidence") else (0, 0)
    return {
        "shipments_scored": int(scored[0] or 0),
        "average_absolute_correction_days": float(scored[1] or 0.0),
        "average_base_late_probability": float(scored[2] or 0.0),
        "high_or_critical_base_risk": int(scored[3] or 0),
        "elevated_or_higher_base_risk": int(scored[4] or 0),
        "tracking_events": int(events[0] or 0),
        "shipments_with_tracking_events": int(events[1] or 0),
        "live_states": int(live[0] or 0),
        "high_or_critical_live_risk": int(live[1] or 0),
        "average_scan_silence_hours": float(live[2] or 0.0),
        "completed_carrier_evidence_rows": int(evidence[0] or 0),
        "carrier_labels_observed": int(evidence[1] or 0),
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def breakdown(db_path: Path, group_by: str, limit: int = 100) -> dict[str, Any]:
    if group_by not in ALLOWED_GROUPS:
        raise ValueError(f"group_by must be one of {sorted(ALLOWED_GROUPS)}")
    limit = max(1, min(int(limit), 1000))
    query = f"""
        SELECT COALESCE(NULLIF({group_by},''),'UNKNOWN') AS group_value,
               COUNT(*) AS shipments,
               AVG(ABS(correction_days)) AS avg_abs_correction,
               AVG(late_probability) AS avg_late_probability,
               SUM(CASE WHEN late_risk_band IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END) AS high_risk
        FROM scored_shipments
        GROUP BY group_value
        ORDER BY shipments DESC, group_value
        LIMIT ?
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    return {
        "group_by": group_by,
        "groups": [
            {
                group_by: r[0],
                "shipments": int(r[1]),
                "average_absolute_correction_days": float(r[2] or 0.0),
                "average_late_probability": float(r[3] or 0.0),
                "high_or_critical_shipments": int(r[4] or 0),
            }
            for r in rows
        ],
    }


def live_alerts(db_path: Path, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(int(limit), 1000))
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "live_shipment_states"):
            return {"count": 0, "alerts": []}
        rows = conn.execute(
            """
            SELECT state_json FROM live_shipment_states
            WHERE live_risk_band IN ('ELEVATED','HIGH','CRITICAL')
            ORDER BY live_late_probability DESC, updated_utc DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    alerts = [json.loads(r[0]) for r in rows]
    return {"count": len(alerts), "alerts": alerts}

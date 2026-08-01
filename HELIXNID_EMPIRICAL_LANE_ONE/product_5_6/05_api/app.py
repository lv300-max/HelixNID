#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve()
LANE_ROOT = HERE.parents[2]
SRC = LANE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import carrier_precision_engine as engine  # noqa: E402

LOCKED_CERT = LANE_ROOT / "reports_olist_eta" / "release_certificate.json"
MODEL_PATH = engine.MODEL_PATH
RUNTIME_DIR = LANE_ROOT / "product_5_6" / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("HELIXNID_DB_PATH", str(RUNTIME_DIR / "carrier_precision.db")))
MAX_BATCH = int(os.getenv("HELIXNID_MAX_BATCH", "10000"))

app = FastAPI(
    title="HELIXNID Carrier Precision API",
    version="1.1.0",
    description="Correct delivery promises, score late risk, persist results, and replay/export shipment evidence.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("HELIXNID_CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class Shipment(BaseModel):
    model_config = ConfigDict(extra="allow")
    shipment_id: str | None = None
    ship_time: str | None = None
    purchase_time: str | None = None
    carrier_handoff_time: str
    carrier_eta_time: str | None = None
    promised_delivery_time: str | None = None
    carrier: str | None = None
    service: str | None = None
    destination: str | None = None
    destination_zip: str | None = None


class BatchRequest(BaseModel):
    shipments: list[Shipment] = Field(min_length=1, max_length=MAX_BATCH)


class RuntimeMetrics:
    def __init__(self):
        self.lock = Lock()
        self.started = datetime.now(timezone.utc)
        self.shipments_scored = 0
        self.high_risk = 0
        self.elevated_or_higher = 0
        self.total_abs_correction_days = 0.0
        self.batch_requests = 0

    def record(self, scored: dict[str, Any]):
        with self.lock:
            self.shipments_scored += 1
            band = scored.get("late_risk_band")
            if band == "HIGH":
                self.high_risk += 1
            if band in {"HIGH", "ELEVATED"}:
                self.elevated_or_higher += 1
            self.total_abs_correction_days += abs(float(scored.get("helixnid_correction_days", 0.0)))

    def record_batch(self):
        with self.lock:
            self.batch_requests += 1

    def snapshot(self):
        with self.lock:
            n = self.shipments_scored
            return {
                "service_started_utc": self.started.isoformat(),
                "shipments_scored_this_process": n,
                "high_risk_shipments_this_process": self.high_risk,
                "elevated_or_higher_shipments_this_process": self.elevated_or_higher,
                "average_absolute_correction_days_this_process": self.total_abs_correction_days / n if n else 0.0,
                "batch_requests_this_process": self.batch_requests,
            }


metrics = RuntimeMetrics()
_model_cache: dict[str, Any] | None = None
_model_lock = Lock()
_db_lock = Lock()


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scored_shipments (
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scored_utc ON scored_shipments(scored_utc)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shipment_id ON scored_shipments(shipment_id)")
        conn.commit()


def persist_score(payload: dict[str, Any], result: dict[str, Any]):
    with _db_lock, db_connect() as conn:
        conn.execute(
            """
            INSERT INTO scored_shipments
            (scored_utc, shipment_id, carrier, service, destination, late_risk_band,
             late_probability, correction_days, confidence, input_json, output_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                result.get("shipment_id"), result.get("carrier"), result.get("service"), result.get("destination"),
                result.get("late_risk_band"), float(result.get("late_probability", 0.0)),
                float(result.get("helixnid_correction_days", 0.0)), result.get("confidence"),
                json.dumps(payload, sort_keys=True), json.dumps(result, sort_keys=True),
            ),
        )
        conn.commit()


def ensure_model() -> dict[str, Any]:
    global _model_cache
    with _model_lock:
        if _model_cache is not None:
            return _model_cache
        if not MODEL_PATH.exists():
            _model_cache = engine.build_model()
        else:
            _model_cache = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        return _model_cache


def raw_score(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return engine.score(payload, ensure_model())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def score_payload(payload: dict[str, Any], persist: bool = True) -> dict[str, Any]:
    result = raw_score(payload)
    metrics.record(result)
    if persist:
        persist_score(payload, result)
    return result


def locked_certificate() -> dict[str, Any]:
    if not LOCKED_CERT.exists():
        return {"status": "MODEL_AVAILABLE_CERTIFICATE_NOT_FOUND", "model_path": str(MODEL_PATH)}
    return json.loads(LOCKED_CERT.read_text(encoding="utf-8"))


def grouped_report(request: BatchRequest, field: str) -> dict[str, Any]:
    scored = [raw_score(s.model_dump(exclude_none=True)) for s in request.shipments]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        key = str(row.get(field) or "UNKNOWN")
        groups[key].append(row)
    report = []
    for key, rows in sorted(groups.items()):
        n = len(rows)
        report.append({
            field: key,
            "shipments": n,
            "average_late_probability": sum(float(r["late_probability"]) for r in rows) / n,
            "average_absolute_correction_days": sum(abs(float(r["helixnid_correction_days"])) for r in rows) / n,
            "high_risk_shipments": sum(r["late_risk_band"] == "HIGH" for r in rows),
            "elevated_or_higher_shipments": sum(r["late_risk_band"] in {"HIGH", "ELEVATED"} for r in rows),
            "average_warning_hours": sum(float(r["warning_window_hours_to_original_eta"]) for r in rows) / n,
        })
    return {"group_by": field, "groups": report, "shipments": len(scored)}


def persisted_count():
    with db_connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM scored_shipments").fetchone()[0])


init_db()


@app.get("/")
def root():
    return {
        "product": "HELIXNID Carrier Precision Meter",
        "api": "v1.1",
        "docs": "/docs",
        "health": "/health",
        "score": "/score-shipment",
        "csv": "/batch-score-csv",
        "history": "/recent",
        "export": "/export.csv",
    }


@app.get("/health")
def health():
    model = ensure_model()
    return {
        "status": "ok",
        "model": model.get("model"),
        "dataset_sha256": model.get("dataset_sha256"),
        "trained_real_completed_orders": model.get("trained_real_completed_orders"),
        "synthetic_rows": model.get("synthetic_rows"),
        "persisted_shipments": persisted_count(),
        "database": str(DB_PATH),
    }


@app.post("/score-shipment")
def score_shipment(shipment: Shipment):
    return score_payload(shipment.model_dump(exclude_none=True))


@app.post("/correct-eta")
def correct_eta(shipment: Shipment):
    r = score_payload(shipment.model_dump(exclude_none=True))
    return {
        "shipment_id": r.get("shipment_id"),
        "original_eta": r["original_eta"],
        "helixnid_corrected_eta": r["helixnid_corrected_eta"],
        "helixnid_correction_days": r["helixnid_correction_days"],
        "confidence": r["confidence"],
        "matched_history_rows": r["matched_history_rows"],
        "model": r["model"],
        "dataset_sha256": r["dataset_sha256"],
    }


@app.post("/late-risk")
def late_risk(shipment: Shipment):
    r = score_payload(shipment.model_dump(exclude_none=True))
    return {
        "shipment_id": r.get("shipment_id"),
        "late_probability": r["late_probability"],
        "late_risk_band": r["late_risk_band"],
        "warning_window_hours_to_original_eta": r["warning_window_hours_to_original_eta"],
        "confidence": r["confidence"],
        "matched_history_rows": r["matched_history_rows"],
    }


@app.post("/batch-score")
def batch_score(request: BatchRequest):
    metrics.record_batch()
    results = [score_payload(s.model_dump(exclude_none=True)) for s in request.shipments]
    return {
        "count": len(results),
        "high_risk": sum(r["late_risk_band"] == "HIGH" for r in results),
        "elevated_or_higher": sum(r["late_risk_band"] in {"HIGH", "ELEVATED"} for r in results),
        "results": results,
    }


@app.post("/batch-score-csv")
async def batch_score_csv(file: UploadFile = File(...)):
    data = await file.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8") from exc
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(status_code=422, detail="CSV contains no shipment rows")
    if len(rows) > MAX_BATCH:
        raise HTTPException(status_code=413, detail=f"CSV exceeds maximum batch size {MAX_BATCH}")
    metrics.record_batch()
    results = [score_payload({k: v for k, v in row.items() if v not in (None, "")}) for row in rows]
    return {
        "filename": file.filename,
        "count": len(results),
        "high_risk": sum(r["late_risk_band"] == "HIGH" for r in results),
        "elevated_or_higher": sum(r["late_risk_band"] in {"HIGH", "ELEVATED"} for r in results),
        "results": results,
    }


@app.post("/carrier-report")
def carrier_report(request: BatchRequest):
    result = grouped_report(request, "carrier")
    result["scope_boundary"] = "Carrier names are integration grouping fields in Olist-trained V1; the empirical model itself does not learn carrier-brand effects."
    return result


@app.post("/route-report")
def route_report(request: BatchRequest):
    return grouped_report(request, "destination")


@app.get("/recent")
def recent(limit: int = 100):
    limit = max(1, min(limit, 1000))
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT scored_utc, output_json FROM scored_shipments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {
        "count": len(rows),
        "results": [{"scored_utc": r["scored_utc"], **json.loads(r["output_json"])} for r in rows],
    }


@app.get("/export.csv")
def export_csv():
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT scored_utc, shipment_id, carrier, service, destination, late_risk_band, late_probability, correction_days, confidence, output_json FROM scored_shipments ORDER BY id"
        ).fetchall()
    out = io.StringIO()
    fields = ["scored_utc", "shipment_id", "carrier", "service", "destination", "late_risk_band", "late_probability", "correction_days", "confidence", "original_eta", "helixnid_corrected_eta", "warning_window_hours_to_original_eta", "dataset_sha256"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        result = json.loads(r["output_json"])
        writer.writerow({
            "scored_utc": r["scored_utc"], "shipment_id": r["shipment_id"], "carrier": r["carrier"], "service": r["service"],
            "destination": r["destination"], "late_risk_band": r["late_risk_band"], "late_probability": r["late_probability"],
            "correction_days": r["correction_days"], "confidence": r["confidence"], "original_eta": result.get("original_eta"),
            "helixnid_corrected_eta": result.get("helixnid_corrected_eta"), "warning_window_hours_to_original_eta": result.get("warning_window_hours_to_original_eta"),
            "dataset_sha256": result.get("dataset_sha256"),
        })
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=helixnid_scored_shipments.csv"})


@app.get("/certificate")
def certificate():
    return {
        "product": "HELIXNID Carrier Precision Meter",
        "empirical_certificate": locked_certificate(),
        "api_scope": "delivery-promise correction and late-risk scoring at carrier handoff",
        "carrier_brand_boundary": "Olist V1 has no FedEx/UPS/DHL carrier identity; carrier/service fields are integration passthrough fields until carrier-labelled evidence is acquired.",
    }


@app.get("/metrics")
def runtime_metrics():
    snap = metrics.snapshot()
    snap["persisted_shipments"] = persisted_count()
    return snap
